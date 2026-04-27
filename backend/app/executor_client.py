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
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def run_command(self, command: ActionCommand) -> Optional[RunCommandResponse]:
        """Forward an ActionCommand to the executor and return the outcome."""
        url = f"{self.base_url}/api/run"
        payload = RunCommandRequest(command=command).model_dump()

        try:
            res = await self._client.post(url, json=payload, headers=self.headers)
            if res.status_code == 401:
                logger.error("Executor auth failed (401).")
                return None

            res.raise_for_status()
            data = res.json()
            try:
                return RunCommandResponse(**data)
            except Exception as ve:
                logger.error(f"Executor response schema mismatch: {ve}")
                logger.error(f"Raw response: {data}")
                return None
        except httpx.ReadTimeout:
            logger.error(f"Executor timed out after {self.timeout}s")
            return None
        except httpx.ConnectError:
            logger.error(f"Could not connect to executor at {url}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected executor client error: {e}")
            return None

executor_client = ExecutorClient(
    base_url=settings.executor_base_url,
    api_key=settings.executor_api_key,
    timeout=settings.executor_timeout_seconds,
)
