"""
Report builder
==============
Assembles one agent run into a self-contained, archived report folder:

  reports/{YYYYMMDD-HHMM}_{lot}_W{wafer}/
    report.md       - the structured report (links images relatively)
    images/*.png    - every rendered wafer image

This separates the *deliverable* (an archived, downloadable report) from the
live event stream shown in the chat. The report is one folder so the images
and their descriptions always travel together.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from agent.config import REPORTS_DIR


@dataclass
class StepRecord:
    """One executed agent step and the material it produced."""
    tool: str
    fact_card: str = ""                                # the tool's text fact card
    analysis: str = ""                                 # the vision-model analysis
    images: list[dict] = field(default_factory=list)   # [{"b64", "label"}]


@dataclass
class ReportData:
    """Everything accumulated during one agent run."""
    user_request: str = ""
    steps: list[StepRecord] = field(default_factory=list)
    conclusion: str = ""


_SECTION_TITLE = {
    "plot_binary_map":     "Binary Pass/Fail Map",
    "plot_pin_properties": "PIN Property Maps",
    "plot_pin_pchart":     "P-Charts",
}

# image display width (px) per tool — property maps are kept small on request
_IMG_WIDTH = {
    "plot_binary_map":     260,
    "plot_pin_properties": 180,
    "plot_pin_pchart":     300,
}


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(text)).strip("_") or "x"


def _facts_table_html(card: str) -> str:
    """Render one fact card as a compact HTML key-value table, shown beside its image."""
    rows: list[str] = []
    for line in card.strip().splitlines():
        line = line.strip()
        if not line or line == "[Wafer Facts]" or line.startswith("Product / Lot"):
            continue
        key, sep, val = line.partition(":")
        if sep:
            rows.append(f"<tr><td><b>{key.strip()}</b></td><td>{val.strip()}</td></tr>")
    return ("<table>" + "".join(rows) + "</table>") if rows else "(no data)"


def _scan_meta(data: ReportData) -> tuple[str, str, str]:
    """Derive (lot, wafer_id, summary_line) from the accumulated fact cards."""
    lot, wafer, summary = "unknown", "NA", ""
    for step in data.steps:
        text = step.fact_card or ""
        m = re.search(r"Product / Lot:\s*(.+)", text)
        if m and lot == "unknown":
            lot = m.group(1).strip()
        m = re.search(r"Wafer\s+(\S+):\s*(yield.+)", text)
        if m:
            if wafer == "NA":
                wafer = m.group(1)
            summary = summary or f"Wafer {m.group(1)}: {m.group(2).strip()}"
    return lot, wafer, summary


def build_report(data: ReportData) -> dict:
    """
    Render the report folder for one agent run.

    Returns {"id", "folder", "report_path"}.
    """
    ts = datetime.now()
    lot, wafer, summary = _scan_meta(data)
    folder_name = f"{ts:%Y%m%d-%H%M}_{_slug(lot)}_W{_slug(wafer)}"
    folder = Path(REPORTS_DIR) / folder_name
    images_dir = folder / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    out: list[str] = [
        "# Wafer Analysis Report",
        "",
        f"**Product / Lot:** {lot} &nbsp;|&nbsp; **Wafer ID:** {wafer}",
        f"**Generated:** {ts:%Y-%m-%d %H:%M}",
        "",
    ]
    if summary:
        out += ["## Summary", "", summary, ""]
    out += ["---", ""]

    # ── one evidence section per step that produced images ─────────────────
    img_seq = 0
    section_no = 0
    for step in data.steps:
        if not step.images:
            continue                                   # e.g. get_wafer_info
        section_no += 1
        title = _SECTION_TITLE.get(step.tool, step.tool)
        width = _IMG_WIDTH.get(step.tool, 260)
        cards = step.fact_card.split("\n\n") if step.fact_card.strip() else []

        out += [f"## {section_no}. {title}", "", f"> *Evidence — `{step.tool}`*", ""]

        # one row per image: the image beside its wafer-facts table
        for i, img in enumerate(step.images):
            img_seq += 1
            fname = f"{img_seq:02d}_{_slug(img.get('label', step.tool))}.png"
            (images_dir / fname).write_bytes(base64.b64decode(img["b64"]))
            facts = _facts_table_html(cards[i] if i < len(cards) else "")
            label = img.get("label", "")
            out += [
                "<table><tr>",
                f'<td valign="top"><img src="images/{fname}" width="{width}" alt="{label}"></td>',
                f'<td valign="top">{facts}</td>',
                "</tr></table>",
                "",
            ]

        if step.analysis.strip():
            out += ["**Analysis**", "", step.analysis.strip(), ""]
        out += ["---", ""]

    # ── conclusion ─────────────────────────────────────────────────────────
    out += ["## Conclusion", "", data.conclusion.strip() or "(no conclusion produced)", ""]

    report_path = folder / "report.md"
    report_path.write_text("\n".join(out), encoding="utf-8")

    return {"id": folder_name, "folder": str(folder), "report_path": str(report_path)}