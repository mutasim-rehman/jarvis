import json
import sys
import os

# Add parent directory to path so we can import shared
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from shared.schema import ActionCommand, AssistantResponse, Task
from shared.workflows import WORKFLOWS
from .llm import generate_chat

SYSTEM_PROMPT = """
You are JARVIS, a professional and proactive AI assistant.
Your goal is to understand user intent and provide a natural response followed by a structural command IF an action is required.

CRITICAL RULES:
1. You MUST ONLY output intents from this list:
   - OPEN_APP
   - HANDLE_ASSIGNMENTS
   - CREATE_PROJECT
   - START_PROJECT
   - GENERAL_CHAT
   - UNKNOWN

2. NEVER include "tasks", "type", or "multi_step" in your JSON.
3. Intent must be a plain string (e.g., "HANDLE_ASSIGNMENTS").
4. If no action is required (e.g., greetings, general questions), DO NOT output JSON.
5. If the user mentions assignments or projects, BE PROACTIVE and trigger the appropriate intent.

FORMAT FOR ACTIONS:
<Conversational message>

{
  "intent": "...",
  "target": "optional"
}

EXAMPLES:
Input: "hello"
Output: "Hello! How can I help you today?"

Input: "do my assignment"
Output: "Alright, I'll set everything up for your assignments.
{
  "intent": "HANDLE_ASSIGNMENTS"
}"

Input: "ive got assignments due"
Output: "I see those assignments. I'll get your environment ready so you can start working right away.
{
  "intent": "HANDLE_ASSIGNMENTS"
}"
"""

async def parse_intent(text: str) -> AssistantResponse:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.strip()},
        {"role": "user", "content": text}
    ]
    
    # We no longer use strict JSON format from Ollama because we want Text + JSON
    response = await generate_chat(messages=messages)
    
    content = response.get("message", {}).get("content", "").strip()
    
    if "{" in content:
        # Split text and JSON
        json_start = content.index("{")
        message = content[:json_start].strip()
        json_part = content[json_start:].strip()
        
        try:
            # Clean up markdown if present
            if json_part.startswith("```json"):
                json_part = json_part[7:-3].strip()
            elif json_part.startswith("```"):
                json_part = json_part[3:-3].strip()
                
            data = json.loads(json_part)
            intent = data.get("intent", "UNKNOWN")
            target = data.get("target")
            
            # Map back to AssistantResponse schema
            command = ActionCommand(intent=intent, target=target)
            
            # Inject tasks from predefined workflows if applicable
            if intent in WORKFLOWS:
                workflow_tasks = WORKFLOWS[intent]
                tasks_to_add = []
                for t in workflow_tasks:
                    task_data = t.copy()
                    # If task target is not specified in workflow, use the one from LLM
                    if task_data.get("target") is None:
                        task_data["target"] = target
                    tasks_to_add.append(Task(**task_data))
                command.tasks = tasks_to_add
                
            parsed_response = AssistantResponse(
                message=message or "Done.",
                command=command
            )
            
            return parsed_response
        except json.JSONDecodeError:
            return AssistantResponse(
                message=content,
                command=None
            )
    else:
        # Pure conversation
        return AssistantResponse(
            message=content,
            command=None
        )


