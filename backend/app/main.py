import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fastapi import Depends, FastAPI, Header, HTTPException

from shared.schema import InteractResponse, ParseRequest, ParseResponse, RouteKind, SCHEMA_VERSION
from .config import settings
from .parser import parse_intent
from .executor_client import executor_client

app = FastAPI(
    title="JARVIS Backend API",
    version=SCHEMA_VERSION,
    description="Phase 1: natural language → structured commands (OpenAPI for clients).",
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


@app.post("/api/parse", response_model=ParseResponse)
async def parse_text(
    request: ParseRequest,
    _: None = Depends(verify_dev_api_key),
):
    command = await parse_intent(request.text)
    return ParseResponse(command=command, original_text=request.text)


@app.post("/api/interact", response_model=InteractResponse)
async def interact(
    request: ParseRequest,
    _: None = Depends(verify_dev_api_key),
):
    """
    Phase 3: Parse natural language and execute the command if applicable.
    Returns both the assistant's message and the execution results.
    """
    # 1. Parse intent
    assistant_resp = await parse_intent(request.text)
    
    execution_result = None
    
    # 2. Execute if a command exists and routing allows it
    if assistant_resp.command and assistant_resp.route == RouteKind.DESKTOP_EXECUTION:
        execution_result = await executor_client.run_command(assistant_resp.command)
        
    return InteractResponse(
        assistant_response=assistant_resp,
        execution_result=execution_result,
        original_text=request.text,
    )
