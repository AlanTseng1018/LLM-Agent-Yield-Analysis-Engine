"""
SOP package.

Standard Operating Procedures are defined as Markdown files in this folder
(one per department, e.g. engineering.md). The agent loads an SOP and runs
its Fixed Steps as a guaranteed evidence chain before adaptive follow-up.
"""
from agent.sop.loader import load_sop

__all__ = ["load_sop"]