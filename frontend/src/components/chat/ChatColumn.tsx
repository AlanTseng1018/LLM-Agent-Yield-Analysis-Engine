import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { ModelSelector } from "./ModelSelector";
import type { ChatMessage } from "../../types/chat";
import "./chat.css";

type ChatColumnProps = {
  messages: ChatMessage[];
  input: string;
  onInputChange: (v: string) => void;
  onSend: () => void;
  onStop: () => void;
  loading: boolean;
  model: string;
  onModelChange: (model: string) => void;
};

export function ChatColumn({
  messages,
  input,
  onInputChange,
  onSend,
  onStop,
  loading,
  model,
  onModelChange,
}: ChatColumnProps) {
  return (
    <div className="chat-column">
      <header className="chat-column__header">
        <span className="chat-column__brand">
          Local Chat ·
          <ModelSelector value={model} onChange={onModelChange} disabled={loading} />
        </span>
        <span className="chat-column__status">{loading ? "Streaming…" : "Ready"}</span>
      </header>
      <MessageList messages={messages} />
      <ChatInput
        value={input}
        onChange={onInputChange}
        onSend={onSend}
        onStop={onStop}
        loading={loading}
      />
    </div>
  );
}
