import os
import sys

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

from fastapi import Depends, FastAPI, Header, HTTPException

from shared.schema import RunCommandRequest, RunCommandResponse, SCHEMA_VERSION
from executor.app.config import settings
from executor.app.runner import run_command_with_allowlist_path

app = FastAPI(
    title="JARVIS Executor API",
    version=SCHEMA_VERSION,
    description="Phase 2: runs structured ActionCommand tasks on the local machine.",
)


async def verify_dev_api_key(
    x_api_key: str | None = Header(default=None, alias=settings.api_key_header),
) -> None:
    if not settings.api_require_auth:
        return
    if not settings.api_dev_token or x_api_key != settings.api_dev_token:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
async def health_check():
    return {"status": "ok", "schema_version": SCHEMA_VERSION}


@app.post("/api/run", response_model=RunCommandResponse)
async def run_tasks(
    request: RunCommandRequest,
    _: None = Depends(verify_dev_api_key),
):
    return run_command_with_allowlist_path(request.command, settings.allowlist_path or None)
