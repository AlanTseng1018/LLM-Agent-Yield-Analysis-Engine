import type { ThinkingNode as ThinkingNodeType } from "../../hooks/useThinkingNodes";
import "./ThinkingPanel.css";

type ThinkingNodeProps = {
  node: ThinkingNodeType;
};

// ── Step card parser ────────────────────────────────────────────────────────
// Matches: "Step 1 — get_wafer_info: Read basic summary"
const STEP_RE = /^Step\s+(\d+)\s*[—–\-]+\s*([\w_]+)\s*:\s*(.+)$/i;
const FILE_RE = /^file_path\s*=\s*(.+)$/i;

type ParsedStep = {
  num: string;
  tool: string;
  reason: string;
  filePath?: string;
};

function parseStep(text: string): ParsedStep | null {
  const lines = text.trim().split("\n");
  const match = lines[0].match(STEP_RE);
  if (!match) return null;

  const fileLine = lines.find((l) => FILE_RE.test(l.trim()));
  const fileMatch = fileLine?.match(FILE_RE);
  const fileName = fileMatch
    ? fileMatch[1].trim().split(/[\\/]/).pop()   // show filename only
    : undefined;

  return {
    num:      match[1],
    tool:     match[2],
    reason:   match[3].trim(),
    filePath: fileName,
  };
}

// ── Plan step card ──────────────────────────────────────────────────────────
function PlanCard({ step, active }: { step: ParsedStep; active: boolean }) {
  return (
    <div className={`plan-card ${active ? "plan-card--active" : "plan-card--done"}`}>
      <div className="plan-card__badge">{active ? step.num : "✓"}</div>
      <div className="plan-card__body">
        <span className="plan-card__tool">{step.tool}</span>
        <span className="plan-card__reason">{step.reason}</span>
        {step.filePath && (
          <span className="plan-card__filepath">📁 {step.filePath}</span>
        )}
      </div>
    </div>
  );
}

// ── Main node ───────────────────────────────────────────────────────────────
export function ThinkingNode({ node }: ThinkingNodeProps) {
  const step = parseStep(node.text);
  const active = node.status === "active";

  if (step) {
    return <PlanCard step={step} active={active} />;
  }

  // Fallback: plain thinking text (unchanged)
  return (
    <div className={`thinking-node ${active ? "thinking-node--active" : ""}`}>
      <div className="thinking-node__dot" />
      <p className="thinking-node__text">{node.text}</p>
    </div>
  );
}
