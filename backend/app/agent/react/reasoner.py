"""
Reasoner
========
The "thinking" half of the ReAct loop.

Wraps a single Ollama tool-calling round: given the running scratchpad,
the model returns EITHER a tool call (the next action) OR a final answer.

Native tool-calling is used instead of text parsing — qwen3:8b advertises
the `tools` capability and was verified to pick tools, react to tool
results and stop reliably across repeated runs.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import httpx

from agent.config import PLANNER_MODEL

OLLAMA_CHAT_URL = os.getenv("OLLAMA_CHAT_URL", "http://127.0.0.1:11434/api/chat")


@dataclass
class ToolCall:
    name: str
    args: dict


@dataclass
class Decision:
    """One reasoning round's outcome."""
    tool_calls: list[ToolCall] = field(default_factory=list)
    content: str = ""    # final answer text, when is_final

    @property
    def is_final(self) -> bool:
        """No tool calls means the planner is done and produced an answer."""
        return not self.tool_calls


async def decide(
    messages: list[dict],
    tools: list[dict],
    model: str = PLANNER_MODEL,
    num_ctx: int = 16384,
) -> Decision:
    """Run one reasoning round and return the next action(s) or a final answer."""
    # num_ctx is generous because the scratchpad accumulates a vision-analysis
    # observation every iteration; num_predict reserves room for the final
    # conclusion so a long scratchpad cannot starve the output.
    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {"num_ctx": num_ctx, "num_predict": 2048},
    }
    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient(timeout=httpx.Timeout(180)) as client:
        resp = await client.post(OLLAMA_CHAT_URL, json=payload)
        resp.raise_for_status()
        msg = resp.json().get("message", {})

    calls = [
        ToolCall(
            name=tc["function"]["name"],
            args=tc["function"].get("arguments") or {},
        )
        for tc in (msg.get("tool_calls") or [])
    ]
    return Decision(tool_calls=calls, content=(msg.get("content") or "").strip())
