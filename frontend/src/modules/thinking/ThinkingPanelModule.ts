import { registerPanel } from "../registry";
import { ThinkingPanel } from "./ThinkingPanel";
import { isAssistantMessage } from "../../types/chat";

registerPanel({
  id: "thinking",
  label: "Thinking",
  component: ThinkingPanel,
  isVisible: ({ messages, isStreaming }) => {
    if (isStreaming) return true;
    // Also keep visible after stream if the last assistant message has thinking content
    const last = [...messages].reverse().find((m) => m.role === "assistant");
    return !!(last && isAssistantMessage(last) && last.thinkingText);
  },
});
