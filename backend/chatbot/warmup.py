"""Warm Hugging Face Space + Gradio client so first user message is not cold-start slow."""
from __future__ import annotations

import logging
import time

from .config import settings
from .providers.huggingface_space import warmup_hf_client

logger = logging.getLogger(__name__)


def warmup_hf_space() -> None:
    if not settings.hf_warmup_on_startup:
        logger.info("hf warmup skipped (HF_WARMUP_ON_STARTUP=false)")
        return
    if not settings.resolved_hf_space_id():
        logger.info("hf warmup skipped (no HF_SPACE_ID)")
        return
    started = time.perf_counter()
    try:
        warmup_hf_client()
        logger.info("hf warmup completed in %.1fms", (time.perf_counter() - started) * 1000)
    except Exception as exc:
        logger.warning("hf warmup failed: %s", exc)
