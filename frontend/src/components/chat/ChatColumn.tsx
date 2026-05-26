import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
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
};

export function ChatColumn({
  messages,
  input,
  onInputChange,
  onSend,
  onStop,
  loading,
  model,
}: ChatColumnProps) {
  return (
    <div className="chat-column">
      <header className="chat-column__header">
        <span className="chat-column__brand">Local Chat · {model}</span>
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
