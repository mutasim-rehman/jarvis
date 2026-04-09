import httpx
from typing import Dict, Any
from .config import settings

async def generate_chat(messages: list[Dict[str, Any]], format: Any = None) -> Dict[str, Any]:
    """Generates a chat response from Ollama API."""
    async with httpx.AsyncClient() as client:
        payload = {
            "model": settings.ollama_model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_ctx": 4096
            }
        }
        if format:
            payload["format"] = format
            
        try:
            response = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise RuntimeError(f"Error communicating with Ollama: {e}")
