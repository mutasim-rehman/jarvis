from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from shared.schema import ActionCommand, RunCommandRequest, SCHEMA_VERSION, Task, TaskResult
from executor.app import main as main_mod
from executor.app import runner as runner_mod
from executor.app.config import Settings
from executor.app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["schema_version"] == SCHEMA_VERSION


def test_run_open_app_mock(monkeypatch):
    called = {}

    def fake(task, ctx):
        called["target"] = task.target
        return TaskResult(action=task.action, success=True, message="ok")

    monkeypatch.setitem(runner_mod._HANDLERS, "OPEN_APP", fake)
    body = RunCommandRequest(
        command=ActionCommand(intent="OPEN_APP", target="notepad", tasks=None),
    ).model_dump()
    r = client.post("/api/run", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["overall_success"] is True
    assert data["schema_version"] == SCHEMA_VERSION
    assert len(data["results"]) == 1
    assert called["target"] == "notepad"


def test_run_open_url_mock(monkeypatch):
    def fake(task, ctx):
        return TaskResult(action=task.action, success=True, message="ok", artifacts={"url": "https://x.test"})

    monkeypatch.setitem(runner_mod._HANDLERS, "OPEN_URL", fake)
    body = RunCommandRequest(
        command=ActionCommand(
            intent="OPEN_WEBSITE",
            target="https://example.com",
            tasks=[Task(action="OPEN_URL", target="https://example.com")],
        ),
    ).model_dump()
    r = client.post("/api/run", json=body)
    assert r.status_code == 200
    assert r.json()["overall_success"] is True


def test_create_folder_path_not_allowed(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    cfg = tmp_path / "allow.yaml"
    cfg.write_text(yaml.dump({"path_roots": [str(allowed)]}), encoding="utf-8")
    ctx = runner_mod.build_context(cfg)
    cmd = ActionCommand(
        intent="HANDLE_ASSIGNMENTS",
        tasks=[Task(action="CREATE_FOLDER", target=str(tmp_path / "forbidden" / "x"))],
    )
    resp = runner_mod.run_command(cmd, ctx)
    assert resp.overall_success is False
    assert resp.results[0].error_code == "PATH_NOT_ALLOWED"


def test_create_folder_success(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    cfg = tmp_path / "allow.yaml"
    cfg.write_text(yaml.dump({"path_roots": [str(allowed)]}), encoding="utf-8")
    ctx = runner_mod.build_context(cfg)
    cmd = ActionCommand(
        intent="X",
        tasks=[Task(action="CREATE_FOLDER", target="nested/dir")],
    )
    resp = runner_mod.run_command(cmd, ctx)
    assert resp.overall_success is True
    assert (allowed / "nested" / "dir").is_dir()


def test_run_not_implemented():
    body = RunCommandRequest(
        command=ActionCommand(
            intent="HANDLE_ASSIGNMENTS",
            tasks=[Task(action="LOGIN", target="gcr")],
        ),
    ).model_dump()
    r = client.post("/api/run", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["overall_success"] is False
    assert data["results"][0]["error_code"] == "NOT_IMPLEMENTED"


def test_synthesize_tasks_open_website():
    cmd = ActionCommand(intent="OPEN_WEBSITE", target="https://a.test", tasks=None)
    tasks = runner_mod.normalize_tasks(cmd)
    assert len(tasks) == 1
    assert tasks[0].action == "OPEN_URL"
    assert tasks[0].target == "https://a.test"


def test_synthesize_default_open_app():
    cmd = ActionCommand(intent="OPEN_APP", target="calc", tasks=None)
    tasks = runner_mod.normalize_tasks(cmd)
    assert tasks[0].action == "OPEN_APP"


def test_requires_api_key_when_enabled(monkeypatch):
    def fake_open_app(task, ctx):
        return TaskResult(action=task.action, success=True, message="ok")

    monkeypatch.setitem(runner_mod._HANDLERS, "OPEN_APP", fake_open_app)
    monkeypatch.setenv("EXECUTOR_API_REQUIRE_AUTH", "true")
    monkeypatch.setenv("EXECUTOR_API_DEV_TOKEN", "secret")
    fresh = Settings()
    monkeypatch.setattr(main_mod, "settings", fresh)
    body = RunCommandRequest(
        command=ActionCommand(intent="OPEN_APP", target="x", tasks=None),
    ).model_dump()
    r = client.post("/api/run", json=body)
    assert r.status_code == 401

    r2 = client.post("/api/run", json=body, headers={"X-API-Key": "secret"})
    assert r2.status_code == 200
