"""
Live comparison: Gemini API vs Hugging Face Space for Jarvis parse_intent use case.

Run from repo root:
  python backend/scripts/compare_chat_providers.py

Requires .env with GOOGLE_GEMINI_KEY (or Google_Gemini_Key) and HF_SPACE_ID.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Cases that bypass heuristics/quick-path and exercise the LLM + JSON pipeline.
# expected_command: intent string or None for chat-only
BENCHMARK_CASES: list[tuple[str, str | None]] = [
    ("tell me a joke", None),
    ("what's happening in technology today", "FETCH_TECH_NEWS"),
    ("could you find something relaxing to listen to while I work", "PLAY_MUSIC"),
    ("launch my code editor", "OPEN_APP"),
    ("I want to watch something funny about cats", "WATCH_VIDEO"),
    ("give me the latest silicon valley updates", "FETCH_TECH_NEWS"),
    ("put on something chill for focus", "PLAY_MUSIC"),
    ("please do my homework for me", None),
    ("open spotify and play jazz", "PLAY_MUSIC"),
    ("what's due on my assignments", "CHECK_ASSIGNMENTS"),
]


_PROVIDER_ERROR_SNIPPETS = (
    "couldn't reach the chatbot",
    "chatbot is unavailable",
    "provider right now",
)


@dataclass
class CaseResult:
    text: str
    expected: str | None
    ok: bool
    intent: str | None
    llm_path: bool
    latency_ms: float
    message_preview: str
    provider_failed: bool = False
    error: str | None = None


def _is_provider_failure(message: str) -> bool:
    lower = (message or "").lower()
    return any(s in lower for s in _PROVIDER_ERROR_SNIPPETS)


def _classify_llm_path(text: str) -> bool:
    from backend.app.heuristics import should_suppress_structured_command
    from backend.app.parser import quick_conversational_response

    if quick_conversational_response(text):
        return False
    if should_suppress_structured_command(text):
        return False
    return True


async def _run_provider(provider: str) -> list[CaseResult]:
    from backend.app.parser import parse_intent

    results: list[CaseResult] = []
    for text, expected in BENCHMARK_CASES:
        uses_llm = _classify_llm_path(text)
        started = time.perf_counter()
        error = None
        intent = None
        message_preview = ""
        provider_failed = False
        try:
            resp = await parse_intent(text, chat_provider=provider)
            latency_ms = (time.perf_counter() - started) * 1000
            intent = resp.command.intent if resp.command else None
            message_preview = (resp.message or "")[:80]
            provider_failed = uses_llm and _is_provider_failure(resp.message or "")
            if not uses_llm:
                ok = True
            elif provider_failed:
                ok = False
            elif expected is None:
                ok = resp.command is None
            else:
                ok = intent == expected
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            error = str(exc)
            provider_failed = True
            ok = False

        results.append(
            CaseResult(
                text=text,
                expected=expected,
                ok=ok,
                intent=intent,
                llm_path=uses_llm,
                latency_ms=round(latency_ms, 1),
                message_preview=message_preview,
                provider_failed=provider_failed,
                error=error,
            )
        )
    return results


def _summarize(provider: str, results: list[CaseResult]) -> dict:
    llm_rows = [r for r in results if r.llm_path]
    llm_ok = sum(1 for r in llm_rows if r.ok)
    provider_failures = sum(1 for r in llm_rows if r.provider_failed or r.error)
    errors = [r for r in results if r.error]
    latencies = [r.latency_ms for r in llm_rows if r.ok]
    return {
        "provider": provider,
        "total": len(results),
        "llm_cases": len(llm_rows),
        "llm_accuracy": f"{llm_ok}/{len(llm_rows)}" if llm_rows else "n/a",
        "provider_failures": provider_failures,
        "errors": len(errors),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "p95_latency_ms": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 1) if latencies else None,
    }


def _print_report(provider: str, results: list[CaseResult], summary: dict) -> None:
    print(f"\n{'=' * 60}")
    print(f"Provider: {provider}")
    print(
        f"LLM-path accuracy: {summary['llm_accuracy']}  |  "
        f"provider_failures: {summary['provider_failures']}  |  errors: {summary['errors']}"
    )
    if summary["avg_latency_ms"] is not None:
        print(f"LLM-path latency: avg {summary['avg_latency_ms']} ms, p95 {summary['p95_latency_ms']} ms")
    print("-" * 60)
    for r in results:
        tag = "LLM" if r.llm_path else "skip"
        status = "OK" if r.ok else "FAIL"
        exp = r.expected or "(no command)"
        got = r.intent or "(no command)"
        print(f"  [{status}] [{tag}] {r.text!r}")
        print(f"         expected={exp} got={got}  {r.latency_ms}ms")
        if r.provider_failed:
            print("         provider call failed (quota/unavailable)")
        if r.error:
            print(f"         error: {r.error[:120]}")
        elif r.message_preview:
            print(f"         msg: {r.message_preview!r}")


async def _probe_gemini() -> str | None:
    from backend.chatbot.providers.gemini import generate_chat_gemini

    try:
        await generate_chat_gemini([{"role": "user", "content": "Reply with exactly: pong"}])
        return None
    except Exception as exc:
        return str(exc)[:200]


async def main() -> int:
    from backend.chatbot.config import settings

    gemini_key = settings.google_gemini_key or os.getenv("Google_Gemini_Key", "").strip()
    hf_space = settings.resolved_hf_space_id()

    print("Jarvis chat provider comparison (live APIs)")
    print(f"  Gemini key configured: {bool(gemini_key)}")
    print(f"  HF space: {hf_space or '(missing)'}")

    if not gemini_key:
        print("\nERROR: Set GOOGLE_GEMINI_KEY in .env for Gemini tests.")
        return 1
    if not hf_space:
        print("\nERROR: Set HF_SPACE_ID or HF_SPACE_LINK for Hugging Face tests.")
        return 1

    if not settings.google_gemini_key and gemini_key:
        os.environ["GOOGLE_GEMINI_KEY"] = gemini_key

    gemini_probe = await _probe_gemini()
    if gemini_probe:
        print(f"\nWARNING: Gemini probe failed: {gemini_probe}")

    all_summaries = []
    for provider in ("gemini", "huggingface"):
        print(f"\nRunning {provider}...")
        results = await _run_provider(provider)
        summary = _summarize(provider, results)
        all_summaries.append((provider, results, summary))
        _print_report(provider, results, summary)

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    for provider, _, summary in all_summaries:
        print(
            f"  {provider:12}  llm_accuracy={summary['llm_accuracy']:>5}  "
            f"errors={summary['errors']}  avg_ms={summary['avg_latency_ms']}"
        )

    g = next(s for p, _, s in all_summaries if p == "gemini")
    h = next(s for p, _, s in all_summaries if p == "huggingface")

    if g["provider_failures"] > 0:
        print(
            "\nGemini could not be fairly compared (API failures). "
            "Fix billing/quota or GOOGLE_GEMINI_KEY, then re-run."
        )
    elif g["llm_accuracy"] != h["llm_accuracy"]:
        winner = "gemini" if g["llm_accuracy"] > h["llm_accuracy"] else "huggingface"
        print(f"\nRecommendation (LLM-path intent accuracy): {winner}")
    elif g.get("avg_latency_ms") and h.get("avg_latency_ms"):
        faster = "gemini" if g["avg_latency_ms"] < h["avg_latency_ms"] else "huggingface"
        print(f"\nSame LLM accuracy; faster on successful LLM cases: {faster}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
