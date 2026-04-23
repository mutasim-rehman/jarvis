import sys
import os
import base64

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from shared.schema import InteractResponse, ParseRequest, ParseResponse, RouteKind, SCHEMA_VERSION
from .config import settings
from .parser import parse_intent
from .executor_client import executor_client
from .stt import transcribe_wav_bytes
from .tts import synthesize_kokoro_wav

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


@app.post("/api/transcribe")
async def transcribe_audio(
    request: Request,
    _: None = Depends(verify_dev_api_key),
):
    audio_bytes = await request.body()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio payload.")

    try:
        text = transcribe_wav_bytes(audio_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"text": text}


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
