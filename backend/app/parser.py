import json
import sys
import os

# Add parent directory to path so we can import shared
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from shared.schema import ActionCommand, CommandType, AssistantResponse, Task
from shared.workflows import WORKFLOWS
from .llm import generate_chat

SYSTEM_PROMPT = """
You are JARVIS, a helpful, conversational AI assistant that can also execute system commands.
Your responses must ALWAYS match the AssistantResponse schema, containing a conversational "message" and an optional structural "command".
You MUST choose an intent ONLY from the valid predefined enums. Do not invent tasks, just provide the correct intent, type, and target/parameters.

IMPORTANT PATTERN YOU SHOULD FOLLOW:

🟢 Case 1 — Pure conversation
Input: "hello!"
{
  "message": "Welcome back. What are we working on today?"
}

🟢 Case 2 — Conversation + Command (Single Step)
Input: "open chrome"
{
  "message": "Opening Chrome for you.",
  "command": {
    "intent": "OPEN_APP",
    "type": "single_step",
    "target": "chrome"
  }
}

🔴 Case 3 — Conversation + Command (Complex Workflow)
Input: "do my pending assignments"
{
  "message": "Alright, I'll set up your assignment environment.",
  "command": {
    "intent": "HANDLE_ASSIGNMENTS",
    "type": "multi_step",
    "target": "gcr"
  }
}

Ensure you always provide a natural conversational response in the 'message' field.
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
        parsed_response = AssistantResponse(**data)
        
        # Inject tasks from predefined workflows if applicable
        if parsed_response.command and parsed_response.command.intent:
            intent_val = parsed_response.command.intent.value
            if intent_val in WORKFLOWS:
                workflow_tasks = WORKFLOWS[intent_val]
                parsed_response.command.tasks = [Task(**task) for task in workflow_tasks]
                
        return parsed_response
    except (KeyError, json.JSONDecodeError) as e:
        # Fallback if parsing fails
        return AssistantResponse(
            message="I'm sorry, I encountered an internal error interpreting that request.",
            command=ActionCommand(intent="UNKNOWN", type=CommandType.SINGLE, target=None, parameters={"error": str(e), "raw": response.get("message", {}).get("content", "")})
        )


