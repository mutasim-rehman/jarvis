import asyncio
import sys
import os
import json

import httpx

# Ensure the root directory is in the sys.path to import 'shared' and 'backend'
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(script_dir, '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from backend.app.parser import parse_intent
from shared.schema import RouteKind, RunCommandRequest


def _executor_base_url() -> str | None:
    if "JARVIS_EXECUTOR_URL" in os.environ:
        url = os.environ["JARVIS_EXECUTOR_URL"].strip()
        return url or None
    return "http://127.0.0.1:8001"


async def _maybe_run_on_executor(command, base_url: str) -> None:
    headers = {}
    token = (os.environ.get("JARVIS_EXECUTOR_API_KEY") or "").strip()
    if token:
        headers["X-API-Key"] = token
    payload = RunCommandRequest(command=command).model_dump(mode="json")
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(f"{base_url.rstrip('/')}/api/run", json=payload, headers=headers)
    except httpx.ConnectError:
        print(
            f"\n(Executor not reachable at {base_url}; skipping run. "
            "Start it with: py -m uvicorn executor.app.main:app --port 8001)\n",
            flush=True,
        )
        return
    if r.status_code == 401:
        print("\n(Executor returned 401; set JARVIS_EXECUTOR_API_KEY if auth is enabled.)\n", flush=True)
        return
    if r.status_code != 200:
        print(f"\n(Executor error HTTP {r.status_code}: {r.text[:500]})\n", flush=True)
        return
    data = r.json()
    ok = data.get("overall_success")
    print(f"\nExecutor: overall_success={ok}", flush=True)
    for res in data.get("results") or []:
        status = "ok" if res.get("success") else "failed"
        extra = ""
        if not res.get("success") and res.get("error_code"):
            extra = f" [{res['error_code']}]"
        print(f"  - {res.get('action')}: {status}{extra} — {res.get('message', '')}", flush=True)
    print(flush=True)


async def main():
    ex_url = _executor_base_url()
    print("===============================")
    print("   JARVIS Phase 1 CLI Tester   ")
    print("===============================")
    print("Type your natural language command below (or 'exit' to quit):")
    print("Note: Ensure Ollama is running locally.")
    if ex_url:
        print(f"Desktop actions will be sent to executor at {ex_url} (set JARVIS_EXECUTOR_URL= to disable).")
    else:
        print("Executor dispatch disabled (JARVIS_EXECUTOR_URL is empty).")
    
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

                if (
                    ex_url
                    and response.route == RouteKind.DESKTOP_EXECUTION
                    and response.command is not None
                ):
                    await _maybe_run_on_executor(response.command, ex_url)

            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {e}", flush=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
