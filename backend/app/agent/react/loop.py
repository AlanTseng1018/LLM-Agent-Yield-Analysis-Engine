"""
ReAct Loop
==========
Orchestrates the Reason -> Act -> Observe cycle.

  Reason   reasoner.decide()      pick the next tool, or finish
  Act      tool_runner.run_tool() execute the tool via the MCP server
  Observe  observation.observe()  render images, run vision analysis and
                                  produce the text observation appended
                                  to the scratchpad

The loop is intentionally tiny and never needs to change — every behaviour
that varies lives in an injected component (reasoner / tool_runner /
observation / policy).

`run_react_agent` yields NDJSON-encoded bytes ready for the frontend.
Event vocabulary: thinking / image / analysis / delta / report / done.
"""
from __future__ import annotations

import json
from typing import AsyncGenerator

from agent.config import DATA_CONTEXT
from agent.react.observation import observe
from agent.react.policy import LoopState, should_stop
from agent.react.reasoner import ToolCall, decide
from agent.react.tool_runner import REACT_TOOLS, run_tool
from agent.report import ReportData, StepRecord, build_report
from agent.sop import load_sop


_SYSTEM = """\
You are an autonomous wafer-analysis agent. You MUST follow the Standard
Operating Procedure (SOP) given below — read all of it before acting.

Work ONE STEP AT A TIME: call a tool, observe its result, then decide the
next action. First complete EVERY Fixed Step of the SOP, in order — this is
the required evidence chain. Do not repeat a step already completed. After
the Fixed Steps, carry out the Adaptive Investigation, then STOP calling
tools and write the conclusion exactly as the SOP requires.

================ SOP: {sop_name} ({sop_department}) ================
{sop_body}
=====================================================================

{data_context}
"""


class Scratchpad:
    """The running message history shared with the planner each round."""

    def __init__(self, user_message: str, sop: str = "engineering"):
        self.sop_meta, sop_body = load_sop(sop)
        system = _SYSTEM.format(
            sop_name=self.sop_meta.get("name", sop),
            sop_department=self.sop_meta.get("department", "—"),
            sop_body=sop_body,
            data_context=DATA_CONTEXT,
        )
        self.messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ]

    def add_tool_calls(self, calls: list[ToolCall]) -> None:
        self.messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": c.name, "arguments": c.args}}
                for c in calls
            ],
        })

    def add_observation(self, text: str) -> None:
        self.messages.append({"role": "tool", "content": text})


def _emit(etype: str, content: str) -> bytes:
    return (json.dumps({"type": etype, "content": content}) + "\n").encode()


def _format_call(call: ToolCall) -> str:
    """Plain, readable representation of a tool call (file_path dropped as noise)."""
    extra = {k: v for k, v in call.args.items() if k != "file_path"}
    if extra:
        return f"{call.name}({json.dumps(extra, ensure_ascii=False)})"
    return call.name


async def _final_summary(
    scratchpad: Scratchpad,
    model: str | None = None,
) -> AsyncGenerator[tuple[str, str], None]:
    """
    Force a concluding answer when the loop hits a safety cap.

    Yields (event_type, content): one "conclusion" event (captured for the
    report) followed by one "delta" event (streamed to the chat).
    """
    scratchpad.messages.append({
        "role": "user",
        "content": (
            "Stop calling tools. Based on everything observed so far, write "
            "the final wafer analysis conclusion now as plain text."
        ),
    })
    try:
        # decide() defaults to PLANNER_MODEL when model is None
        kwargs = {"model": model} if model else {}
        decision = await decide(scratchpad.messages, tools=[], **kwargs)
        text = decision.content or "(no conclusion produced)"
    except Exception as e:
        text = f"\n[Could not produce final summary: {e}]\n"
    yield ("conclusion", text)
    yield ("delta", text)


async def run_react_agent(
    user_message: str,
    model: str | None = None,
) -> AsyncGenerator[bytes, None]:
    """Full ReAct agent. Yields NDJSON bytes: thinking / image / analysis / delta / done.

    `model` overrides both the planner and the vision model. Pass None to
    keep the defaults from agent/config.py (PLANNER_MODEL / VISION_MODEL).
    """
    # ── load the SOP first — the agent's whole run is driven by it ─────────
    try:
        scratchpad = Scratchpad(user_message)
    except Exception as e:
        yield _emit("delta", f"\n[SOP load failed: {e}]\n")
        yield (json.dumps({"type": "done", "meta": {}}) + "\n").encode()
        return

    m = scratchpad.sop_meta
    yield _emit(
        "thinking",
        f"Loaded SOP: {m.get('name', 'engineering')} "
        f"({m.get('department', '—')}) — following the standard procedure.\n\n",
    )

    state = LoopState()
    summary_context = ""   # wafer-info text, handed to the vision model as context
    report_data = ReportData(user_request=user_message)

    while True:
        # ── safety caps ───────────────────────────────────────────────────
        stop_reason = should_stop(state)
        if stop_reason:
            yield _emit("thinking", f"Stopping: {stop_reason}.\n\n")
            async for etype, content in _final_summary(scratchpad, model=model):
                if etype == "conclusion":
                    report_data.conclusion = content
                else:
                    yield _emit(etype, content)
            break

        state.iteration += 1

        # ── REASON ────────────────────────────────────────────────────────
        try:
            kwargs = {"model": model} if model else {}
            decision = await decide(scratchpad.messages, REACT_TOOLS, **kwargs)
        except Exception as e:
            yield _emit("delta", f"\n[Reasoner failed: {e}]\n")
            break

        # ── natural stop: planner produced a final answer ─────────────────
        if decision.is_final:
            yield _emit("thinking", "Enough evidence gathered — writing the conclusion.\n\n")
            report_data.conclusion = decision.content or "(no answer produced)"
            yield _emit("delta", report_data.conclusion)
            break

        # ── ACT + OBSERVE: print each tool call, then run it ──────────────
        scratchpad.add_tool_calls(decision.tool_calls)
        for call in decision.tool_calls:
            yield _emit("thinking", f"Step {state.iteration}: {_format_call(call)}\n\n")
            result = await run_tool(call.name, call.args)
            if result.error:
                state.errors += 1

            observation_text = ""
            step_analysis: list[str] = []
            async for etype, content in observe(result, summary_context, model=model):
                if etype == "observation":
                    observation_text = content
                elif etype == "image":
                    img = json.loads(content)
                    yield (json.dumps({
                        "type": "image",
                        "url": img["url"],
                        "label": img.get("label", ""),
                    }) + "\n").encode()
                else:  # "analysis"
                    step_analysis.append(content)
                    yield _emit(etype, content)

            # first successful wafer-info text becomes vision-model context
            if call.name == "get_wafer_info" and not result.error:
                summary_context = result.text

            scratchpad.add_observation(observation_text)
            report_data.steps.append(StepRecord(
                tool=call.name,
                fact_card=result.text,
                analysis="".join(step_analysis),
                images=result.images,
            ))

    # ── build the archived report folder ───────────────────────────────────
    if report_data.steps:
        try:
            info = build_report(report_data)
            yield (json.dumps({"type": "report", "id": info["id"]}) + "\n").encode()
        except Exception as e:
            yield _emit("thinking", f"Report build failed: {e}\n\n")

    yield (json.dumps({"type": "done", "meta": {}}) + "\n").encode()
