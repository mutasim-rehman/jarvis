import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from fastapi import FastAPI
from shared.schema import ParseRequest, ParseResponse
from .parser import parse_intent

app = FastAPI(title="JARVIS Backend API")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/parse", response_model=ParseResponse)
async def parse_text(request: ParseRequest):
    command = await parse_intent(request.text)
    return ParseResponse(
        command=command,
        original_text=request.text
    )
