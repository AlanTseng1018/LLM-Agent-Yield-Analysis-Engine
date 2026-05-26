type StreamHandlers = {
  onDelta?: (t: string) => void;
  onPostDelta?: (t: string) => void;
  onThinking?: (t: string) => void;
  onImage?: (url: string, label: string) => void;
  onAnalysis?: (t: string) => void;
  onReport?: (id: string) => void;
  onDone?: (meta?: unknown) => void;
  onError?: (e: unknown) => void;
};

export async function streamChat(
  endpoint: string,
  body: unknown,
  handlers: StreamHandlers,
  signal?: AbortSignal
) {
  const res = await fetch(`${endpoint}?debug=1`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok || !res.body) {
    const detail = await res.text().catch(() => "");
    handlers.onError?.({ message: `HTTP ${res.status}`, detail });
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buf += decoder.decode(value, { stream: true });

    let nl: number;
    while ((nl = buf.indexOf("\n")) !== -1) {
      const raw = buf.slice(0, nl);
      buf = buf.slice(nl + 1);
      const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
      if (!line) continue;

      try {
        const obj = JSON.parse(line);

        switch (obj.type) {
          case "delta":
            if (obj.content) handlers.onDelta?.(obj.content);
            break;
          case "thinking":
            if (obj.content) handlers.onThinking?.(obj.content);
            break;
          case "image":
            if (obj.url) handlers.onImage?.(obj.url, obj.label ?? "");
            break;
          case "analysis":
            if (obj.content) handlers.onAnalysis?.(obj.content);
            break;
          case "postdelta":
            if (obj.content) handlers.onPostDelta?.(obj.content);
            break;
          case "report":
            if (obj.id) handlers.onReport?.(obj.id);
            break;
          case "done":
            handlers.onDone?.(obj.meta);
            break;
          case "error":
            handlers.onError?.(obj);
            break;
        }
      } catch {
        handlers.onDelta?.(line);
      }
    }
  }

  if (buf.trim().length) {
    try {
      const tail = buf.endsWith("\r") ? buf.slice(0, -1) : buf;
      const obj = JSON.parse(tail);

      if (obj?.type === "delta" && obj.content) handlers.onDelta?.(obj.content);
      else if (obj?.type === "thinking" && obj.content) handlers.onThinking?.(obj.content);
      else if (obj?.type === "done") handlers.onDone?.(obj.meta);
    } catch {
      handlers.onDelta?.(buf);
    }
  }
}