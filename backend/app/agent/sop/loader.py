"""
SOP loader
==========
Loads a Standard Operating Procedure from a Markdown file in this folder.

Each department owns one SOP file (e.g. engineering.md). The file has YAML
front-matter (name, department, version) followed by the SOP body — Fixed
Steps, execution rules, adaptive guidance and conclusion requirements.
"""
from __future__ import annotations

from pathlib import Path

SOP_DIR = Path(__file__).parent


def load_sop(name: str = "engineering") -> tuple[dict, str]:
    """
    Load an SOP Markdown file by name (without the .md extension).

    Returns
    -------
    (metadata, body)
        metadata : front-matter parsed into a dict (name, department, …)
        body     : the Markdown content after the front-matter
    """
    path = SOP_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"SOP file not found: {path}")

    text = path.read_text(encoding="utf-8")
    meta: dict = {}
    body = text

    # ── parse the simple `--- ... ---` front-matter, if present ────────────
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            front = text[3:end]
            body = text[end + 4:].lstrip()
            for line in front.strip().splitlines():
                key, sep, value = line.partition(":")
                if sep:
                    meta[key.strip()] = value.strip()

    return meta, body