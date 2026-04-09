import asyncio
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(script_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import json
from backend.app.parser import parse_intent
from backend.app.llm import generate_chat
from shared.schema import ActionCommand, IntentType

async def try_parse():
    messages = [
        {"role": "system", "content": "You are JARVIS..."},
        {"role": "user", "content": "open arc browser"}
    ]
    schema = ActionCommand.model_json_schema()
    try:
        import httpx
        from backend.app.config import settings
        
        payload = {
            "model": settings.ollama_model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_ctx": 4096
            },
            "format": schema
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{settings.ollama_base_url}/api/chat", json=payload)
            print("Status:", resp.status_code)
            print("Body:", resp.text)
    except Exception as e:
        print("Error:", e)

asyncio.run(try_parse())
