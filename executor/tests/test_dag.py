import pytest

from executor.app.dag import _apply_inputs_from, _execution_layers, run_tasks_dag
from shared.schema import Task, TaskResult
from executor.app.context import HandlerContext


def test_execution_layers_respects_dependencies():
    tasks = [
        Task(id="step1", action="OPEN_APP", target="chrome"),
        Task(id="step2", action="OPEN_URL", target="https://x.test", depends_on=["step1"]),
    ]
    layers = _execution_layers(tasks)
    assert len(layers) == 2
    assert layers[0][0].id == "step1"
    assert layers[1][0].id == "step2"


def test_inputs_from_resolves_target():
    outputs = {"step1": {"output": {"url": "https://resolved.test"}}}
    task = Task(
        id="step2",
        action="OPEN_URL",
        inputs_from={"target": "step1.output.url"},
    )
    resolved = _apply_inputs_from(task, outputs)
    assert resolved.target == "https://resolved.test"


def test_run_dag_skips_after_dependency_failure():
    def ok_handler(task, ctx):
        return TaskResult(action=task.action, task_id=task.id, success=True, message="ok", output={"url": "u"})

    def fail_handler(task, ctx):
        return TaskResult(action=task.action, task_id=task.id, success=False, error_code="X", message="fail")

    handlers = {"OPEN_APP": ok_handler, "OPEN_URL": fail_handler, "PLAY_MUSIC": ok_handler}
    tasks = [
        Task(id="step1", action="OPEN_APP", target="chrome"),
        Task(id="step2", action="OPEN_URL", target="https://x.test", depends_on=["step1"]),
        Task(id="step3", action="PLAY_MUSIC", depends_on=["step2"]),
    ]
    ctx = HandlerContext(path_roots=[], apps={}, url_aliases={}, settings=None)
    resp = run_tasks_dag(tasks, ctx, handlers)
    assert resp.overall_success is False
    assert any(r.error_code == "DEPENDENCY_FAILED" for r in resp.results)
