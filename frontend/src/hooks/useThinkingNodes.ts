import { useMemo } from "react";

export type ThinkingNodeStatus = "active" | "done";

export type ThinkingNode = {
  id: string;
  text: string;
  status: ThinkingNodeStatus;
};

/**
 * Derives a list of ThinkingNodes from raw thinking text.
 * Splits on double-newlines (\n\n). The last segment is "active"
 * while streaming; all segments become "done" once isDone is true.
 */
export function useThinkingNodes(thinkingText: string, isDone: boolean): ThinkingNode[] {
  return useMemo(() => {
    if (!thinkingText) return [];

    const segments = thinkingText.split(/\n\n+/).filter((s) => s.trim().length > 0);
    if (segments.length === 0) return [];

    return segments.map((text, i) => ({
      id: `node-${i}`,
      text: text.trim(),
      status: isDone || i < segments.length - 1 ? "done" : "active",
    }));
  }, [thinkingText, isDone]);
}
