"""
Live provider comparison (opt-in).

  set RUN_LIVE_PROVIDER_TESTS=1
  py -3 -m pytest backend/tests/test_provider_comparison_live.py -v -s

Or run the full report script:
  py -3 backend/scripts/compare_chat_providers.py
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_PROVIDER_TESTS", "").strip() != "1",
    reason="Set RUN_LIVE_PROVIDER_TESTS=1 to hit live Gemini/HF APIs",
)


@pytest.fixture
def comparison_results():
    from backend.scripts.compare_chat_providers import BENCHMARK_CASES, _run_provider, _summarize

    async def _run():
        gemini_key = os.getenv("GOOGLE_GEMINI_KEY") or os.getenv("Google_Gemini_Key", "")
        if gemini_key:
            os.environ.setdefault("GOOGLE_GEMINI_KEY", gemini_key)
        hf = os.getenv("HF_SPACE_ID") or os.getenv("HF_SPACE_LINK", "")
        if not gemini_key or not hf:
            pytest.skip("GOOGLE_GEMINI_KEY and HF_SPACE_ID/HF_SPACE_LINK required")
        gemini_results = await _run_provider("gemini")
        hf_results = await _run_provider("huggingface")
        return {
            "gemini": (_summarize("gemini", gemini_results), gemini_results),
            "huggingface": (_summarize("huggingface", hf_results), hf_results),
        }

    return asyncio.run(_run())


def test_huggingface_beats_gemini_on_llm_accuracy_or_gemini_unavailable(comparison_results):
    g_summary, _ = comparison_results["gemini"]
    h_summary, _ = comparison_results["huggingface"]

    if g_summary["provider_failures"] > 0:
        pytest.skip(f"Gemini unavailable: {g_summary['provider_failures']} LLM-path failures")

    assert h_summary["llm_accuracy"] >= g_summary["llm_accuracy"]
