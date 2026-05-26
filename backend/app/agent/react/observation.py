"""
ObservationBuilder
==================
Turns a tool's raw result into the text observation fed back to the planner.

Key design choice: the planner (qwen3:8b) is text-only, so images never
enter the scratchpad. Rendered images are analysed by the vision model and
ONLY the resulting text becomes the observation. That analysis text is what
lets the planner reason about what an image actually showed and decide the
next step accordingly.
"""
from __future__ import annotations

import json
from typing import AsyncGenerator

from agent.vision_analyst import stream_image_analysis, stream_pin_batch_analysis
from agent.react.tool_runner import ToolResult


async def observe(
    result: ToolResult,
    summary_context: str,
    model: str | None = None,
) -> AsyncGenerator[tuple[str, str], None]:
    """
    Async-generate (event_type, content) pairs:

      ("image", json_str)    - one per rendered image, forwarded to the frontend
      ("analysis", chunk)    - vision-model analysis tokens, forwarded to frontend
      ("observation", text)  - ALWAYS the LAST event: the text the planner sees

    The caller forwards image/analysis events and keeps the observation text.
    `model` overrides the vision model; None keeps VISION_MODEL from config.
    """
    # ── tool error → the error itself becomes the observation ──────────────
    if result.error:
        yield ("observation", f"ERROR: {result.error}")
        return

    # ── text-only tool (e.g. get_wafer_info) → kept internal, not shown ────
    if not result.images:
        yield ("observation", result.text or "(tool returned no output)")
        return

    # ── image tool → forward images, then run vision analysis ──────────────
    for img in result.images:
        yield ("image", json.dumps({
            "url": f"data:image/png;base64,{img['b64']}",
            "label": img["label"],
        }))

    # The tool's own fact card (exact yield / IQR stats / scale bounds) is the
    # best context for the vision model — it sees the numbers as text instead
    # of guessing them off the pixels. Fall back to the generic wafer summary.
    vlm_context = result.text or summary_context

    vl_kwargs = {"model": model} if model else {}
    analysis_parts: list[str] = []
    try:
        if len(result.images) == 1:
            img = result.images[0]
            async for ttype, chunk in stream_image_analysis(
                img["b64"], img["label"], vlm_context, **vl_kwargs
            ):
                if ttype == "content":
                    analysis_parts.append(chunk)
                    yield ("analysis", chunk)
        else:
            async for ttype, chunk in stream_pin_batch_analysis(
                result.images, vlm_context, **vl_kwargs
            ):
                if ttype == "content":
                    analysis_parts.append(chunk)
                    yield ("analysis", chunk)
    except Exception as e:
        yield ("analysis", f"\n[vision analysis failed: {e}]\n")

    analysis_text = "".join(analysis_parts).strip()
    labels = ", ".join(img["label"] for img in result.images)

    # planner observation = fact card (numbers) + vision analysis (spatial read)
    parts: list[str] = []
    if result.text:
        parts.append(result.text)
    if analysis_text:
        parts.append(f"Vision analysis ({labels}):\n{analysis_text}")
    else:
        parts.append(f"Rendered: {labels} (vision analysis unavailable)")
    yield ("observation", "\n\n".join(parts))
