import { ThinkingTimeline } from "./ThinkingTimeline";
import { useThinkingNodes } from "../../hooks/useThinkingNodes";
import type { PanelModuleProps } from "../registry";
import { isAssistantMessage } from "../../types/chat";
import "./ThinkingPanel.css";

export function ThinkingPanel({ messages, activeMessageIndex, isStreaming }: PanelModuleProps) {
  // Show thinking from the active streaming message, or the last assistant message
  const targetIndex =
    activeMessageIndex !== null
      ? activeMessageIndex
      : [...messages].reverse().findIndex((m) => isAssistantMessage(m) && m.thinkingText);

  const resolvedIndex =
    activeMessageIndex !== null
      ? activeMessageIndex
      : targetIndex === -1
      ? -1
      : messages.length - 1 - targetIndex;

  const target = resolvedIndex >= 0 ? messages[resolvedIndex] : null;
  const thinkingText = (target && isAssistantMessage(target) ? target.thinkingText : "") ?? "";
  const thinkingDone = !isStreaming || (target && isAssistantMessage(target) ? !!target.thinkingDone : true);

  const nodes = useThinkingNodes(thinkingText, thinkingDone);

  return (
    <div className="thinking-panel">
      <div className="thinking-panel__header">
        <span>Planning</span>
        {!thinkingDone && <span className="thinking-panel__live">● live</span>}
      </div>
      {nodes.length === 0 ? (
        <div className="thinking-panel__empty">
          {isStreaming ? "Waiting for thinking…" : "No thinking data"}
        </div>
      ) : (
        <ThinkingTimeline nodes={nodes} />
      )}
    </div>
  );
}
