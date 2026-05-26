import type React from "react";
import "./chat.css";

type ChatInputProps = {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onStop: () => void;
  loading: boolean;
};

export function ChatInput({ value, onChange, onSend, onStop, loading }: ChatInputProps) {
  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <footer className="chat-input">
      <input
        className="chat-input__field"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="輸入訊息，按 Enter 送出"
        disabled={loading}
      />
      {loading ? (
        <button className="chat-input__btn chat-input__btn--stop" onClick={onStop}>
          停止
        </button>
      ) : (
        <button className="chat-input__btn" onClick={onSend}>
          送出
        </button>
      )}
    </footer>
  );
}
