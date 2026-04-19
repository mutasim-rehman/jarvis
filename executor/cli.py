"""Run the executor API with Uvicorn (repo root must be on PYTHONPATH)."""

import os
import sys

import uvicorn

if __name__ == "__main__":
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from executor.app.config import settings

    uvicorn.run(
        "executor.app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
