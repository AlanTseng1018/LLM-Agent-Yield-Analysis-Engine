"""
Vision Analyst
==============
Streams wafer-image analysis from a vision LLM (Ollama).

Public API
----------
stream_image_analysis(image_b64, image_label, summary_text)
    Analyse a single image immediately after it is rendered.
    Yields (token_type, chunk):
      "content"  → final answer  → chat bubble
      "thinking" → CoT tokens    → ThinkingPanel (never shown in bubble)

stream_analysis(images_b64, summary_text)
    Full multi-image analysis (legacy, kept for compatibility).
    Same yield contract as stream_image_analysis.

Internal
--------
_stream_filtered(payload)
    Handles BOTH Ollama's native `thinking` field AND inline <think>…</think>
    blocks that some models embed inside `content`.
"""

from __future__ import annotations

import json
import os
from typing import AsyncGenerator

import httpx

# ── Configuration ──────────────────────────────────────────────────────────
OLLAMA_CHAT_URL = os.getenv("OLLAMA_CHAT_URL", "http://127.0.0.1:11434/api/chat")

# Default model: env var → config.py → hardcoded fallback
def _default_vision_model() -> str:
    env = os.getenv("VISION_MODEL")
    if env:
        return env
    try:
        from agent.config import VISION_MODEL
        return VISION_MODEL
    except ImportError:
        return "qwen3-vl:latest"

VISION_MODEL = _default_vision_model()

# ── System prompts ─────────────────────────────────────────────────────────
_SYSTEM_FULL = """\
You are a senior wafer process engineer.
Language rule (highest priority): ALL output must be in English only.

Based on the wafer measurement summary, binary pass/fail map, and PIN property maps,
output the following four sections using Markdown level-2 headings (##):

## Yield & Fail Distribution
- Spatial pattern of fail die (edge-concentrated / center / random / banded) with reasoning.

## PIN Uniformity
- Evaluate each PIN for spatial gradients or abnormal clusters; identify the most critical PIN.

## Root Cause Inference
- Most likely process issue based on the observed patterns (e.g. edge effect, contamination, tool drift).

## Recommended Actions
- 2–3 highest-priority engineering actions.

Format: bullet points, each under 20 words, no preamble or closing remarks.\
"""

_SYSTEM_SINGLE = """\
You are a senior wafer process engineer.
Language rule (highest priority): ALL output must be in English only.

Numeric facts (product/lot, yield, IQR statistics, colour-scale bounds) are
supplied as text under a "[Wafer Facts]" heading. Treat them as ground truth —
do NOT re-derive or guess numbers from the image. Interpret the SPATIAL
pattern only.

For the provided wafer image, output exactly this structure:

**Spatial Distribution**
- (1 point: describe the fail/anomaly distribution pattern)

**Likely Process Issue**
- (1–2 points: direct engineering judgment)

**Recommended Action**
- (1 point)

Format: each bullet under 15 words, no preamble, no repeated image description.\
"""


# ── Internal stream helper ─────────────────────────────────────────────────

_OPEN_TAG  = "<think>"
_CLOSE_TAG = "</think>"

async def _stream_filtered(
    payload: dict,
) -> AsyncGenerator[tuple[str, str], None]:
    """
    Stream content from Ollama, silently discarding all thinking tokens:
      - Ollama native 'thinking' field      → discarded
      - Inline <think>…</think> in content  → discarded
      - Normal content text                 → ("content", chunk)

    Uses a rolling buffer to handle tags that span chunk boundaries.
    """
    buf      = ""
    in_think = False
    open_len  = len(_OPEN_TAG)
    close_len = len(_CLOSE_TAG)

    async with httpx.AsyncClient(timeout=httpx.Timeout(None)) as client:
        async with client.stream("POST", OLLAMA_CHAT_URL, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg = obj.get("message") or {}

                # Native thinking field — discard entirely
                # (msg.get("thinking") is intentionally ignored)

                raw = msg.get("content", "")
                if raw:
                    buf += raw
                    result = ""

                    while buf:
                        if not in_think:
                            idx = buf.find(_OPEN_TAG)
                            if idx == -1:
                                # No open tag found; safe to yield all but the
                                # last (open_len - 1) chars in case the tag
                                # spans the next chunk.
                                cutoff = max(0, len(buf) - (open_len - 1))
                                result += buf[:cutoff]
                                buf     = buf[cutoff:]
                                break
                            else:
                                result += buf[:idx]          # content before tag
                                buf     = buf[idx + open_len:]
                                in_think = True
                        else:
                            idx = buf.find(_CLOSE_TAG)
                            if idx == -1:
                                # Still inside think block; discard but keep
                                # tail in case </think> spans the next chunk.
                                buf = buf[max(0, len(buf) - (close_len - 1)):]
                                break
                            else:
                                buf      = buf[idx + close_len:]
                                in_think = False

                    if result:
                        yield ("content", result)

                if obj.get("done"):
                    # Flush any remaining buffered content
                    if not in_think and buf:
                        yield ("content", buf)
                    break


# ── Public API ─────────────────────────────────────────────────────────────

def _build_single_prompt(image_label: str, summary_text: str) -> str:
    """Build a targeted user prompt for a single-image analysis call."""
    label = image_label.lower()
    if "binary" in label or "pass" in label or "fail" in label:
        task = "Analyse this Binary Pass/Fail Map using the specified format."
    elif "pin" in label:
        task = f"Analyse this {image_label} property map using the specified format."
    else:
        task = "Analyse this wafer image using the specified format."

    ctx = f"{summary_text.strip()}\n\n" if summary_text.strip() else ""
    return f"{ctx}{task}"


async def stream_image_analysis(
    image_b64: str,
    image_label: str = "",
    summary_text: str = "",
    model: str = VISION_MODEL,
    num_ctx: int = 8192,
) -> AsyncGenerator[tuple[str, str], None]:
    """
    Analyse a single wafer image and stream (token_type, chunk) pairs.

    Designed for interleaved rendering: call immediately after each image
    is yielded so analysis appears right below its corresponding image.

    Parameters
    ----------
    image_b64    : Pure base64 PNG string (no 'data:…' prefix).
    image_label  : Human-readable label, e.g. "Binary pass/fail map" or "PIN_1 property map".
    summary_text : Wafer stats text for context (yield, counts …).
    """
    print(f"[VL] analysing: {image_label or 'image'}", flush=True)

    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_SINGLE},
            {
                "role": "user",
                "content": _build_single_prompt(image_label, summary_text),
                "images": [image_b64],
            },
        ],
        "stream": True,
        "think": False,
        "options": {"num_ctx": num_ctx},
    }

    async for token_type, chunk in _stream_filtered(payload):
        yield token_type, chunk


async def stream_pin_batch_analysis(
    pin_images: list[dict],
    summary_text: str = "",
    model: str = VISION_MODEL,
    num_ctx: int = 8192,
) -> AsyncGenerator[tuple[str, str], None]:
    """
    Analyse all PIN property-map images together in a single VL call.

    Called after ALL property images for a tool step have been yielded to
    the frontend, so the model sees the full set at once.

    Parameters
    ----------
    pin_images   : List of {"b64": str, "label": str} dicts.
    summary_text : Wafer stats text for context.
    """
    labels = [img["label"] for img in pin_images]
    print(f"[VL] batch PIN analysis: {labels}", flush=True)

    ctx        = f"{summary_text.strip()}\n\n" if summary_text.strip() else ""
    label_list = ", ".join(labels) if labels else "PIN maps"
    prompt = (
        f"{ctx}"
        f"The following {len(pin_images)} images are (in order): {label_list}.\n\n"
        "For each PIN property map, output exactly this format:\n\n"
        "### [PIN name]\n"
        "- **Uniformity**: (spatial distribution, gradients or clusters)\n"
        "- **Anomalous Region**: (location and characteristics, or 'None detected')\n"
        "- **Root Cause**: (most likely process reason)\n\n"
        "After all PINs, output:\n\n"
        "### Overall Conclusion\n"
        "- (2 points: cross-PIN common issues and top-priority action)"
    )

    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_SINGLE},
            {
                "role": "user",
                "content": prompt,
                "images": [img["b64"] for img in pin_images],
            },
        ],
        "stream": True,
        "think": False,
        "options": {"num_ctx": num_ctx},
    }

    async for token_type, chunk in _stream_filtered(payload):
        yield token_type, chunk


async def stream_analysis(
    images_b64: list[str],
    summary_text: str,
    model: str = VISION_MODEL,
    think: bool = False,
    num_ctx: int = 8192,
) -> AsyncGenerator[tuple[str, str], None]:
    """
    Full multi-image analysis (used when all images should be analysed together).
    Kept for compatibility; prefer stream_image_analysis / stream_pin_batch_analysis.
    """
    print(f"[VL] full analysis: {len(images_b64)} image(s)", flush=True)

    user_text = (
        "以下是 wafer 量測摘要：\n\n"
        f"{summary_text.strip()}\n\n"
        "請根據上方數據與附圖進行分析。"
    )

    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_FULL},
            {"role": "user", "content": user_text, "images": images_b64},
        ],
        "stream": True,
        "think": think,
        "options": {"num_ctx": num_ctx},
    }

    async for token_type, chunk in _stream_filtered(payload):
        yield token_type, chunk
