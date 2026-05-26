import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "../types/chat";
import { isAssistantMessage } from "../types/chat";
import { streamChat } from "../services/chatStream";

type UseChatOptions = {
  model: string;
  endpoint: string;
};

export function useChat({ model, endpoint }: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "system",
      content: "You are a helpful assistant. Internal reasoning must be in English.",
    },
    { role: "assistant", content: "Hi! need help?" },
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const newUserMsg: ChatMessage = { role: "user", content: text };
    const history = [...messages, newUserMsg];

    setMessages(history);
    setInput("");
    setLoading(true);

    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content: "",
        thinkingText: "",
        thinkingDone: false,
        images: [],
        postContent: "",
      },
    ]);

    const assistantIndex = history.length;

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    const payload = {
      model,
      messages: history,
      options: { num_ctx: 2048 },
    };

    try {
      await streamChat(
        endpoint,
        payload,
        {
          onDelta: (chunk) => {
            setMessages((prev) => {
              const next = [...prev];
              const cur = next[assistantIndex];
              if (cur && isAssistantMessage(cur)) {
                next[assistantIndex] = {
                  ...cur,
                  content: (cur.content || "") + chunk,
                };
              }
              return next;
            });
          },

          onImage: (url, label) => {
            setMessages((prev) => {
              const next = [...prev];
              const cur = next[assistantIndex];
              if (cur && isAssistantMessage(cur)) {
                next[assistantIndex] = {
                  ...cur,
                  images: [...(cur.images ?? []), { url, label, analysis: "" }],
                };
              }
              return next;
            });
          },

          onAnalysis: (chunk) => {
            setMessages((prev) => {
              const next = [...prev];
              const cur = next[assistantIndex];
              if (cur && isAssistantMessage(cur)) {
                const imgs = [...(cur.images ?? [])];
                if (imgs.length > 0) {
                  const last = imgs[imgs.length - 1];
                  imgs[imgs.length - 1] = {
                    ...last,
                    analysis: last.analysis + chunk,
                  };
                  next[assistantIndex] = { ...cur, images: imgs };
                }
              }
              return next;
            });
          },

          onPostDelta: (chunk) => {
            setMessages((prev) => {
              const next = [...prev];
              const cur = next[assistantIndex];
              if (cur && isAssistantMessage(cur)) {
                next[assistantIndex] = {
                  ...cur,
                  postContent: (cur.postContent || "") + chunk,
                };
              }
              return next;
            });
          },

          onThinking: (tchunk) => {
            setMessages((prev) => {
              const next = [...prev];
              const cur = next[assistantIndex];
              if (cur && isAssistantMessage(cur)) {
                next[assistantIndex] = {
                  ...cur,
                  thinkingText: (cur.thinkingText || "") + tchunk,
                };
              }
              return next;
            });
          },

          onReport: (id) => {
            setMessages((prev) => {
              const next = [...prev];
              const cur = next[assistantIndex];
              if (cur && isAssistantMessage(cur)) {
                next[assistantIndex] = { ...cur, reportId: id };
              }
              return next;
            });
          },

          onDone: () => {
            setLoading(false);
            setMessages((prev) => {
              const next = [...prev];
              const cur = next[assistantIndex];
              if (cur && isAssistantMessage(cur)) {
                next[assistantIndex] = { ...cur, thinkingDone: true };
              }
              return next;
            });
          },

          onError: (e: unknown) => {
            setLoading(false);
            setMessages((prev) => {
              const next = [...prev];
              const cur = next[assistantIndex];
              if (cur && isAssistantMessage(cur)) {
                const err = e as { message?: string; detail?: string };
                next[assistantIndex] = {
                  ...cur,
                  content:
                    (cur.content || "") +
                    `\n（發生錯誤）${err?.message || "stream error"}${
                      err?.detail ? ` — ${err.detail}` : ""
                    }`,
                };
              }
              return next;
            });
          },
        },
        abortRef.current.signal
      );
    } catch (err: unknown) {
      if ((err as { name?: string })?.name !== "AbortError") {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `（發生錯誤）${String(err)}` },
        ]);
      }
    } finally {
      setLoading(false);
    }
  };

  const stop = () => {
    abortRef.current?.abort();
    setLoading(false);
  };

  return { messages, input, setInput, loading, send, stop };
}
