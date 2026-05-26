import { useEffect, useRef } from "react";
import { ThinkingNode } from "./ThinkingNode";
import type { ThinkingNode as ThinkingNodeType } from "../../hooks/useThinkingNodes";
import "./ThinkingPanel.css";

type ThinkingTimelineProps = {
  nodes: ThinkingNodeType[];
};

export function ThinkingTimeline({ nodes }: ThinkingTimelineProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [nodes.length]);

  return (
    <div className="thinking-timeline">
      <div className="thinking-timeline__track">
        {nodes.map((node) => (
          <ThinkingNode key={node.id} node={node} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
