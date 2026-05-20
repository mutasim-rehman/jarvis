"""DAG task execution: dependencies, output passing, parallel layers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from typing import Any, Callable

from shared.schema import RunCommandResponse, Task, TaskResult

from executor.app.context import HandlerContext

HandlerFn = Callable[[Task, HandlerContext], TaskResult]


def _ensure_task_ids(tasks: list[Task]) -> list[Task]:
    out: list[Task] = []
    for i, task in enumerate(tasks):
        tid = (task.id or "").strip() or f"step{i + 1}"
        out.append(task.model_copy(update={"id": tid}))
    return out


def _resolve_ref(ref: str, outputs: dict[str, dict[str, Any]]) -> Any:
    """
    Resolve 'step1.output.url' or 'step1.artifacts.path' against completed step outputs.
    """
    parts = ref.strip().split(".")
    if len(parts) < 3:
        return None
    step_id, bucket = parts[0], parts[1]
    if bucket not in ("output", "artifacts"):
        return None
    step_data = outputs.get(step_id) or {}
    container = step_data.get(bucket) or {}
    cur: Any = container
    for key in parts[2:]:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _apply_inputs_from(task: Task, outputs: dict[str, dict[str, Any]]) -> Task:
    if not task.inputs_from:
        return task
    data = task.model_dump()
    for field, ref in task.inputs_from.items():
        value = _resolve_ref(str(ref), outputs)
        if value is None:
            continue
        if field == "target":
            data["target"] = str(value)
        elif field.startswith("parameters."):
            param_key = field.split(".", 1)[1]
            params = dict(data.get("parameters") or {})
            params[param_key] = value
            data["parameters"] = params
        elif field in ("parameters",):
            if isinstance(value, dict):
                data["parameters"] = {**(data.get("parameters") or {}), **value}
        else:
            data[field] = value
    return Task.model_validate(data)


def _execution_layers(tasks: list[Task]) -> list[list[Task]]:
    by_id = {t.id: t for t in tasks if t.id}
    if len(by_id) != len(tasks):
        return [tasks]

    indegree = {tid: 0 for tid in by_id}
    children: dict[str, list[str]] = {tid: [] for tid in by_id}
    for task in tasks:
        tid = task.id or ""
        for dep in task.depends_on:
            if dep in by_id:
                indegree[tid] += 1
                children[dep].append(tid)

    layers: list[list[Task]] = []
    ready = [tid for tid, deg in indegree.items() if deg == 0]
    visited = 0
    while ready:
        layer = [by_id[tid] for tid in ready]
        layers.append(layer)
        visited += len(ready)
        next_ready: list[str] = []
        for tid in ready:
            for child in children.get(tid, []):
                indegree[child] -= 1
                if indegree[child] == 0:
                    next_ready.append(child)
        ready = next_ready

    if visited != len(tasks):
        return [tasks]
    return layers


def _result_output(result: TaskResult) -> dict[str, Any]:
    if result.output:
        return dict(result.output)
    if result.artifacts:
        return dict(result.artifacts)
    return {}


def _run_one(
    task: Task,
    ctx: HandlerContext,
    handlers: dict[str, HandlerFn],
    outputs: dict[str, dict[str, Any]],
) -> TaskResult:
    resolved = _apply_inputs_from(task, outputs)
    handler = handlers.get(resolved.action)
    if handler is None:
        return TaskResult(
            action=resolved.action,
            task_id=resolved.id,
            success=False,
            error_code="NOT_IMPLEMENTED",
            message=f"Action {resolved.action} is not implemented.",
        )
    result = handler(resolved, ctx)
    if result.task_id is None:
        result = result.model_copy(update={"task_id": resolved.id})
    if result.success and not result.output:
        result = result.model_copy(update={"output": _result_output(result)})
    return result


def uses_dag_execution(tasks: list[Task]) -> bool:
    if len(tasks) <= 1:
        return False
    return any(t.depends_on or t.inputs_from or t.id for t in tasks)


def run_tasks_dag(
    tasks: list[Task],
    ctx: HandlerContext,
    handlers: dict[str, HandlerFn],
) -> RunCommandResponse:
    tasks = _ensure_task_ids(tasks)
    layers = _execution_layers(tasks)
    outputs: dict[str, dict[str, Any]] = {}
    results: list[TaskResult] = []
    failed_ids: set[str] = set()

    for layer in layers:
        runnable: list[Task] = []
        for task in layer:
            tid = task.id or ""
            if any(dep in failed_ids for dep in task.depends_on):
                results.append(
                    TaskResult(
                        action=task.action,
                        task_id=tid,
                        success=False,
                        error_code="DEPENDENCY_FAILED",
                        message=f"Skipped {task.action}: dependency did not succeed.",
                    )
                )
                failed_ids.add(tid)
                continue
            runnable.append(task)

        if not runnable:
            continue

        if len(runnable) == 1:
            result = _run_one(runnable[0], ctx, handlers, outputs)
            results.append(result)
            tid = runnable[0].id or ""
            if result.success:
                outputs[tid] = {"output": result.output, "artifacts": result.artifacts}
            else:
                failed_ids.add(tid)
            continue

        with ThreadPoolExecutor(max_workers=min(len(runnable), 4)) as pool:
            futures = {
                pool.submit(_run_one, task, ctx, handlers, deepcopy(outputs)): task
                for task in runnable
            }
            for future in as_completed(futures):
                task = futures[future]
                tid = task.id or ""
                try:
                    result = future.result()
                except Exception as exc:
                    result = TaskResult(
                        action=task.action,
                        task_id=tid,
                        success=False,
                        error_code="HANDLER_EXCEPTION",
                        message=str(exc),
                    )
                results.append(result)
                if result.success:
                    outputs[tid] = {"output": result.output, "artifacts": result.artifacts}
                else:
                    failed_ids.add(tid)

    order = {t.id: i for i, t in enumerate(tasks)}
    results.sort(key=lambda r: order.get(r.task_id, 9999))

    overall = all(r.success for r in results) and len(results) == len(tasks)
    return RunCommandResponse(overall_success=overall, results=results)
