import asyncio
import sys
import os
import json

# Ensure the root directory is in the sys.path to import 'shared' and 'backend'
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(script_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from backend.app.parser import parse_intent

async def main():
    print("===============================")
    print("   JARVIS Phase 1 CLI Tester   ")
    print("===============================")
    print("Type your natural language command below (or 'exit' to quit):")
    print("Note: Ensure Ollama is running locally.")
    
    while True:
        try:
            text = input("\n> ")
            if text.lower() in ("exit", "quit", "q"):
                break
            if not text.strip():
                continue
                
            print("Parsing intent...", flush=True)
            response = await parse_intent(text)

            msg = response.message.strip()
            if len(msg) >= 2 and msg[0] == msg[-1] and msg[0] in "\"'":
                msg = msg[1:-1].strip()

            print(f"\n{msg}\n", flush=True)
            if response.command:
                command = response.command
                print(f"{{")
                print(f'  "intent": "{command.intent}",')
                if command.target:
                    print(f'  "target": "{command.target}",')
                
                if command.tasks:
                    print(f'  "tasks": [')
                    for i, task in enumerate(command.tasks):
                        task_dict = task.model_dump(exclude_none=True)
                        comma = "," if i < len(command.tasks)-1 else ""
                        print(f"    {json.dumps(task_dict)}{comma}")
                    print(f'  ]')
                
                if command.parameters:
                    print(f'  "parameters": {json.dumps(command.parameters)}')
                print(f"}}", flush=True)

            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {e}", flush=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
