import json
import sys
import os

# Add parent directory to path so we can import shared
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from shared.schema import ActionCommand, CommandType, AssistantResponse
from .llm import generate_chat

SYSTEM_PROMPT = """
You are JARVIS, a helpful, conversational AI assistant that can also execute system commands.
Your responses must ALWAYS match the AssistantResponse schema, containing a conversational "message" and an optional structural "command".

IMPORTANT PATTERN YOU SHOULD FOLLOW:

🟢 Case 1 — Pure conversation
Input: "hello!"
{
  "message": "Welcome back. What are we working on today?"
}

🟢 Case 2 — Conversation + Simple Action
Input: "open chrome"
{
  "message": "Opening Chrome for you.",
  "command": {
    "intent": "OPEN_APP",
    "type": "single_step",
    "target": "chrome"
  }
}

🔴 Case 3 — Conversation + Complex Task Pipeline
Input: "do my pending assignments"
{
  "message": "Alright, I'll set up your assignment environment.",
  "command": {
    "intent": "HANDLE_ASSIGNMENTS",
    "type": "multi_step",
    "tasks": [
      {"action": "OPEN_APP", "target": "chrome"},
      {"action": "OPEN_URL", "target": "https://gcr.example.com"},
      {"action": "LOGIN", "target": "gcr"},
      {"action": "FETCH_PENDING_ASSIGNMENTS"}
    ]
  }
}

If the task requires multiple logical steps to achieve, use 'multi_step' and outline them in 'tasks'. Tasks can contain extra fields if necessary like 'duration', 'destination' etc.
For simple single intents, use 'single_step' and provide 'target'. Ensure you always provide a natural conversational response in the 'message' field.

Return your response AS A VALID JSON OBJECT matching the schema format. Do not include any other text or markdown block formatting, just raw JSON.
"""

async def parse_intent(text: str) -> AssistantResponse:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.strip()},
        {"role": "user", "content": text}
    ]
    
    schema = AssistantResponse.model_json_schema()
    
    response = await generate_chat(messages=messages, format=schema)
    
    try:
        content = response["message"]["content"]
        # Clean up possible markdown code blocks
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
            
        data = json.loads(content)
        return AssistantResponse(**data)
    except (KeyError, json.JSONDecodeError) as e:
        # Fallback if parsing fails
        return AssistantResponse(
            message="I'm sorry, I encountered an internal error interpreting that request.",
            command=ActionCommand(intent="UNKNOWN", type=CommandType.SINGLE, target=None, parameters={"error": str(e), "raw": response.get("message", {}).get("content", "")})
        )

