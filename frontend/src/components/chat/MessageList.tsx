import { useEffect, useRef } from "react";
import { MessageBubble } from "./MessageBubble";
import type { ChatMessage } from "../../types/chat";
import "./chat.css";

type MessageListProps = {
  messages: ChatMessage[];
};

export function MessageList({ messages }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <main className="message-list">
      {messages.map((m, i) => (
        <MessageBubble key={i} message={m} />
      ))}
      <div ref={bottomRef} />
    </main>
  );
}
