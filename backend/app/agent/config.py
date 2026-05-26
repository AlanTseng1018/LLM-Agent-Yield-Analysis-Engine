"""
Agent configuration
===================
Single place to edit knobs that govern the ReAct agent's behaviour:
models, data path, safety caps, and report output directory.
"""

# ── Models ────────────────────────────────────────────────────────────────────
# qwen3.5:4b is a unified vision-language model (capabilities: tools + vision),
# so a single model serves BOTH the planner and the vision-analysis roles —
# no second model, no model swapping.
PLANNER_MODEL = "qwen3.5:4b"
VISION_MODEL  = "qwen3.5:4b"

# ── Data ──────────────────────────────────────────────────────────────────────
import os as _os
_REPO_ROOT = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))

DEFAULT_FILE = _os.environ.get(
    "WAFER_DATA_FILE",
    _os.path.join(_REPO_ROOT, "raw_data_example", "wafer_data", "sample_1.zip"),
)

DATA_CONTEXT = (
    "Sample data available at:\n"
    f"  {DEFAULT_FILE}\n"
    "  Format: ZIP containing one CSV with columns: BIN, X, Y, WAFER_ID, PIN_1~PIN_5\n"
    "  Use this path as file_path when tools require it."
)

# ── ReAct loop ────────────────────────────────────────────────────────────────
# Safety caps for the step-by-step agent loop (agent/react/).
REACT_MAX_ITERS  = 12   # hard limit on reasoning rounds (SOP fixed steps + adaptive)
REACT_MAX_ERRORS = 3    # abort after this many failed tool calls

# ── Reports ───────────────────────────────────────────────────────────────────
# Each analysis is archived as a self-contained folder (report.md + images/)
# under this directory at the project root.
REPORTS_DIR = _os.path.join(_REPO_ROOT, "reports")
