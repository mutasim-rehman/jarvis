import json
import sys
import os

# Add parent directory to path so we can import shared
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from shared.schema import ActionCommand, IntentType
from .llm import generate_chat

SYSTEM_PROMPT = """
You are JARVIS, a helpful AI that interprets natural language into structured execution commands.
Categorize the user's request into one of the following intents:
- OPEN_APP: to open or launch an application. Provide the application name in 'target'.
- OPEN_PATH: to open a folder, file, or website URL. Provide the path or URL in 'target'.
- SEARCH_WEB: to perform a web search. Provide the query in 'target'.
- UNKNOWN: if the request doesn't match any known intent.

Return your response AS A VALID JSON OBJECT matching the schema format. Do not include any other text or markdown block formatting, just raw JSON.
"""

async def parse_intent(text: str) -> ActionCommand:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.strip()},
        {"role": "user", "content": text}
    ]
    
    schema = ActionCommand.model_json_schema()
    
    response = await generate_chat(messages=messages, format=schema)
    
    try:
        content = response["message"]["content"]
        # Clean up possible markdown code blocks
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
            
        data = json.loads(content)
        return ActionCommand(**data)
    except (KeyError, json.JSONDecodeError) as e:
        # Fallback if parsing fails
        return ActionCommand(intent=IntentType.UNKNOWN, target=None, parameters={"error": str(e), "raw": response.get("message", {}).get("content", "")})
