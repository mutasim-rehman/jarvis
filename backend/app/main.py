import sys
import os
import base64
import logging
import time
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from shared.schema import InteractResponse, ParseRequest, ParseResponse, RouteKind, SCHEMA_VERSION
from .config import settings
from .parser import parse_intent
from .executor_client import executor_client
from .stt import transcribe_wav_bytes, warmup_model
from .tts import synthesize_kokoro_wav

app = FastAPI(
    title="JARVIS Backend API",
    version=SCHEMA_VERSION,
    description="Phase 1: natural language → structured commands (OpenAPI for clients).",
)
logger = logging.getLogger(__name__)


def _log_executor_task_result(task: asyncio.Task) -> None:
    try:
        result = task.result()
        logger.info("executor background completed has_result=%s", bool(result))
    except Exception:
        logger.exception("executor background task failed")


@app.on_event("startup")
async def on_startup() -> None:
    try:
        warmup_model()
    except Exception as exc:  # pragma: no cover - warmup depends on local model availability
        logger.warning("stt warmup skipped: %s", exc)


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
    if request.chat_provider:
        command = await parse_intent(request.text, chat_provider=request.chat_provider)
    else:
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
    request_started = time.perf_counter()
    # 1. Parse intent
    parse_started = time.perf_counter()
    if request.chat_provider:
        assistant_resp = await parse_intent(request.text, chat_provider=request.chat_provider)
    else:
        assistant_resp = await parse_intent(request.text)
    parse_ms = (time.perf_counter() - parse_started) * 1000
    
    execution_result = None
    
    # 2. Execute if a command exists and routing allows it
    execute_ms = 0.0
    if assistant_resp.command and assistant_resp.route == RouteKind.DESKTOP_EXECUTION:
        execute_started = time.perf_counter()
        run_task = asyncio.create_task(executor_client.run_command(assistant_resp.command))
        try:
            execution_result = await asyncio.wait_for(
                asyncio.shield(run_task),
                timeout=max(0.1, settings.executor_inline_wait_seconds),
            )
            execute_ms = (time.perf_counter() - execute_started) * 1000
        except asyncio.TimeoutError:
            run_task.add_done_callback(_log_executor_task_result)
            execute_ms = (time.perf_counter() - execute_started) * 1000
            assistant_resp.meta["execution_pending"] = True
            logger.info(
                "interact execution deferred inline_wait_s=%.2f",
                settings.executor_inline_wait_seconds,
            )
    logger.info(
        "interact timing parse_ms=%.1f execute_ms=%.1f total_ms=%.1f route=%s has_command=%s",
        parse_ms,
        execute_ms,
        (time.perf_counter() - request_started) * 1000,
        assistant_resp.route,
        bool(assistant_resp.command),
    )
        
    return InteractResponse(
        assistant_response=assistant_resp,
        execution_result=execution_result,
        original_text=request.text,
    )


@app.post("/api/transcribe")
async def transcribe_audio(
    request: Request,
    _: None = Depends(verify_dev_api_key),
):
    started = time.perf_counter()
    audio_bytes = await request.body()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio payload.")

    try:
        text = transcribe_wav_bytes(audio_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info("transcribe timing total_ms=%.1f bytes=%d chars=%d", elapsed_ms, len(audio_bytes), len(text))
    return {"text": text, "meta": {"timing_ms": round(elapsed_ms, 2)}}


class TtsRequest(BaseModel):
    text: str = Field(min_length=1)
    voice: str | None = None
    speed: float | None = None


@app.post("/api/tts")
async def synthesize_tts(
    request: TtsRequest,
    _: None = Depends(verify_dev_api_key),
):
    try:
        wav_bytes, sample_rate = synthesize_kokoro_wav(
            text=request.text,
            voice=request.voice,
            speed=request.speed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "audio_base64": base64.b64encode(wav_bytes).decode("ascii"),
        "sample_rate": sample_rate,
        "format": "wav",
        "voice": request.voice or settings.tts_kokoro_voice,
    }
