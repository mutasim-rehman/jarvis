import asyncio
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(script_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from backend.app.parser import parse_intent

async def main():
    try:
        command = await parse_intent("open arc browser")
        print("\n[Structured Output]")
        print(f"Intent: {command.intent.value}")
        print(f"Target: {command.target}")
        print(f"Param:  {command.parameters}")
    except Exception as e:
        print("Error:", e)

asyncio.run(main())
