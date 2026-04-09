import asyncio
import sys
import os

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
                
            print("Parsing intent...")
            command = await parse_intent(text)
            
            print("\n[Structured Output]")
            print(f"Intent: {command.intent.value}")
            print(f"Target: {command.target}")
            print(f"Param:  {command.parameters}")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
