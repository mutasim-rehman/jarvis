import httpx
import logging
from typing import Optional

from shared.schema import ActionCommand, RunCommandRequest, RunCommandResponse
from .config import settings

logger = logging.getLogger(__name__)

class ExecutorClient:
    """Phase 3 client for communicating with the desktop executor API."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.headers = {
            settings.api_key_header: self.api_key,
            "Content-Type": "application/json",
        }

    async def run_command(self, command: ActionCommand) -> Optional[RunCommandResponse]:
        """Forward an ActionCommand to the executor and return the outcome."""
        url = f"{self.base_url}/api/run"
        payload = RunCommandRequest(command=command).model_dump()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = client.post(url, json=payload, headers=self.headers)
                # Note: httpx.AsyncClient returns a coroutine for post, but wait...
                # I should use 'await client.post(...)'
                res = await response
                
                if res.status_code == 401:
                    logger.error("Executor authentication failed (401).")
                    return None
                
                res.raise_for_status()
                return RunCommandResponse(**res.json())
        except httpx.ConnectError:
            logger.error(f"Could not connect to executor at {url}. Is it running?")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"Executor returned error {e.response.status_code}: {e.response.text}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error calling executor: {e}")
            return None

executor_client = ExecutorClient(
    base_url=settings.executor_base_url,
    api_key=settings.executor_api_key,
    timeout=settings.executor_timeout_seconds,
)
