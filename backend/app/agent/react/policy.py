"""
StopPolicy
==========
Safety limits for the ReAct loop.

The *natural* stop — the planner returning a final answer with no tool
calls — is handled by the loop itself. This policy only enforces SAFETY
caps so a misbehaving planner cannot loop or fail forever.
"""
from __future__ import annotations

from dataclasses import dataclass

from agent.config import REACT_MAX_ITERS, REACT_MAX_ERRORS


@dataclass
class LoopState:
    iteration: int = 0    # reasoning rounds completed
    errors: int = 0       # failed tool calls so far


def should_stop(state: LoopState) -> str | None:
    """Return a human-readable stop reason, or None to keep looping."""
    if state.iteration >= REACT_MAX_ITERS:
        return f"reached max iterations ({REACT_MAX_ITERS})"
    if state.errors >= REACT_MAX_ERRORS:
        return f"too many tool errors ({REACT_MAX_ERRORS})"
    return None
