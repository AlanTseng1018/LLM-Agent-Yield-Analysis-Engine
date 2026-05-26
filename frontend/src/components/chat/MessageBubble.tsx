import { MarkdownMessage } from "../markdown";
import type { ChatMessage } from "../../types/chat";
import { isAssistantMessage } from "../../types/chat";
import "./chat.css";

type MessageBubbleProps = {
  message: ChatMessage;
};

export function MessageBubble({ message: m }: MessageBubbleProps) {
  if (m.role === "system") return null;

  const postContent = isAssistantMessage(m) ? (m.postContent ?? "") : "";
  const reportId    = isAssistantMessage(m) ? m.reportId : undefined;

  return (
    <div className={`bubble ${m.role === "user" ? "bubble--user" : "bubble--bot"}`}>
      <MarkdownMessage text={m.content} />
      {/* wafer images are shown in the Report panel, not in the chat */}
      {postContent && <MarkdownMessage text={postContent} />}
      {reportId && (
        <a
          className="report-download"
          href={`http://localhost:8000/report/${reportId}/download`}
        >
          ⬇ Download report (.zip)
        </a>
      )}
    </div>
  );
}
