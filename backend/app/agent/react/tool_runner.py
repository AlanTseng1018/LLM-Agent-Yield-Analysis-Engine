"""
ToolRunner
==========
The ReAct agent's tool vocabulary.

Exposes a curated set of *logical* tools to the planner and translates each
one into one or more MCP server calls. The mega-tool `run_wafer_analysis`
is deliberately NOT exposed here — if it were, the planner would call it
once and the step-by-step loop would collapse into a single shot.

`plot_pin_properties` is a batch tool: one logical action renders the
property maps for every requested PIN by issuing several MCP calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from mcp_client.client import call_tool


@dataclass
class ToolResult:
    """Outcome of one logical tool call."""
    text: str = ""                                    # textual output (e.g. wafer info)
    images: list[dict] = field(default_factory=list)  # [{"b64": str, "label": str}]
    error: str | None = None


# ── Tool schemas handed to the planner (Ollama tool-calling format) ─────────
REACT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_wafer_info",
            "description": (
                "Read the basic wafer summary: yield, pass/fail counts and the "
                "list of available PIN columns. Call this FIRST, before plotting."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the .csv or .zip wafer file"},
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plot_binary_map",
            "description": (
                "Render the binary pass/fail wafer map to inspect the spatial "
                "distribution of failing dies (edge ring, centre, random …)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the .csv or .zip wafer file"},
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plot_pin_properties",
            "description": (
                "Render continuous-value property maps for the given PIN columns "
                "in one batch call. Pass the PIN names returned by get_wafer_info."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the .csv or .zip wafer file"},
                    "pin_columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": 'PIN columns to plot, e.g. ["PIN_1","PIN_2","PIN_3"]',
                    },
                },
                "required": ["file_path", "pin_columns"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plot_pin_pchart",
            "description": (
                "Render normal-probability P-charts for the given PIN columns "
                "in one batch call (one chart per PIN). Pass the PIN names "
                "returned by get_wafer_info."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the .csv or .zip wafer file"},
                    "pin_columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": 'PIN columns to chart, e.g. ["PIN_1","PIN_2","PIN_3"]',
                    },
                },
                "required": ["file_path", "pin_columns"],
            },
        },
    },
]


def _split_items(items: list[dict], default_label: str) -> ToolResult:
    """Split raw MCP content items into a ToolResult (text + images)."""
    result = ToolResult()
    texts: list[str] = []
    pending_label = default_label
    for it in items:
        if it.get("type") == "text" and it.get("text"):
            txt = it["text"].strip()
            if txt.startswith("#"):                 # heading labels the next image
                pending_label = txt.lstrip("#").strip()
            else:
                texts.append(txt)
        elif it.get("type") == "image" and it.get("data"):
            result.images.append({"b64": it["data"], "label": pending_label})
            pending_label = default_label
    result.text = "\n".join(texts)
    return result


async def run_tool(tool_name: str, args: dict) -> ToolResult:
    """Execute a logical ReAct tool by delegating to the MCP server."""
    file_path = args.get("file_path")
    try:
        if tool_name == "get_wafer_info":
            items = await call_tool("get_wafer_info", {"file_path": file_path})
            return _split_items(items, "wafer info")

        if tool_name == "plot_binary_map":
            items = await call_tool("plot_wafer_bin", {"file_path": file_path})
            return _split_items(items, "Binary pass/fail map")

        if tool_name == "plot_pin_properties":
            pins = args.get("pin_columns") or []
            if not pins:
                return ToolResult(error="plot_pin_properties needs a non-empty pin_columns list")
            merged = ToolResult()
            cards: list[str] = []
            for pin in pins:
                items = await call_tool(
                    "plot_wafer_property", {"file_path": file_path, "pin_column": pin}
                )
                sub = _split_items(items, f"{pin} property map")
                for img in sub.images:
                    img["label"] = f"{pin} property map"
                merged.images.extend(sub.images)
                if sub.text:                       # per-PIN fact card
                    cards.append(sub.text)
            merged.text = "\n\n".join(cards)
            return merged

        if tool_name == "plot_pin_pchart":
            pins = args.get("pin_columns") or []
            if not pins:
                return ToolResult(error="plot_pin_pchart needs a non-empty pin_columns list")
            merged = ToolResult()
            cards: list[str] = []
            for pin in pins:
                items = await call_tool(
                    "plot_pchart", {"file_path": file_path, "pin_column": pin}
                )
                sub = _split_items(items, f"{pin} P-chart")
                for img in sub.images:
                    img["label"] = f"{pin} P-chart"
                merged.images.extend(sub.images)
                if sub.text:                       # per-PIN fact card
                    cards.append(sub.text)
            merged.text = "\n\n".join(cards)
            return merged

        return ToolResult(error=f"Unknown tool: {tool_name}")
    except Exception as e:
        return ToolResult(error=f"{tool_name} failed: {e}")
