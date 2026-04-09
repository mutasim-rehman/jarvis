import asyncio
import httpx

async def main():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get('http://localhost:11434/')
            print("localhost:", resp.status_code)
    except Exception as e:
        print("localhost failed:", type(e).__name__, e)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get('http://127.0.0.1:11434/')
            print("127.0.0.1:", resp.status_code)
    except Exception as e:
        print("127.0.0.1 failed:", type(e).__name__, e)

asyncio.run(main())
