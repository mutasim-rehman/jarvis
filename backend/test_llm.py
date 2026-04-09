import asyncio
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(script_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from backend.app.llm import generate_chat

async def main():
    messages = [{"role": "user", "content": "Just say the word 'hello'"}]
    try:
        response = await generate_chat(messages)
        print("Response:", response)
    except Exception as e:
        print("Error:", e)

asyncio.run(main())
