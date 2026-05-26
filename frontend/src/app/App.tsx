import { useEffect, useState } from "react";

// Side-effect imports: register the right-panel modules
import "../modules/thinking/ThinkingPanelModule";
import "../modules/report/ReportPanelModule";

import { useChat } from "../hooks/useChat";
import { ChatColumn } from "../components/chat/ChatColumn";
import { getRegisteredPanels } from "../modules/registry";
import { isAssistantMessage } from "../types/chat";
import "./App.css";

const MODEL = "qwen3:8b";
const ENDPOINT = "http://localhost:8000/agent/stream";

export default function App() {
  const { messages, input, setInput, loading, send, stop } = useChat({
    model: MODEL,
    endpoint: ENDPOINT,
  });

  const activeMessageIndex = loading ? messages.length - 1 : null;
  const panelProps = { messages, activeMessageIndex, isStreaming: loading };
  const visiblePanels = getRegisteredPanels().filter((p) => p.isVisible(panelProps));
  const showRightPanel = visiblePanels.length > 0;

  // ── right-panel tabs ──────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState("");

  // a streaming run → show Planning
  useEffect(() => {
    if (loading) setActiveTab("thinking");
  }, [loading]);

  // a newly produced report → switch to Report
  let latestReportId: string | null = null;
  for (let i = messages.length - 1; i >= 0 && !latestReportId; i--) {
    const m = messages[i];
    if (isAssistantMessage(m) && m.reportId) latestReportId = m.reportId;
  }
  useEffect(() => {
    if (latestReportId) setActiveTab("report");
  }, [latestReportId]);

  const activePanel =
    visiblePanels.find((p) => p.id === activeTab) ?? visiblePanels[0];

  // ── resizable right panel ─────────────────────────────────────────────────
  const [rightWidth, setRightWidth] = useState(480);

  const startResize = () => {
    const onMove = (e: MouseEvent) => {
      const w = window.innerWidth - e.clientX;
      setRightWidth(Math.max(300, Math.min(w, window.innerWidth - 360)));
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      document.body.style.userSelect = "";
    };
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  return (
    <div
      className={`app-layout${showRightPanel ? " app-layout--split" : ""}`}
      style={{
        gridTemplateColumns: showRightPanel ? `1fr 6px ${rightWidth}px` : "1fr",
      }}
    >
      <ChatColumn
        messages={messages}
        input={input}
        onInputChange={setInput}
        onSend={send}
        onStop={stop}
        loading={loading}
        model={MODEL}
      />

      {showRightPanel && activePanel && (
        <>
          <div className="resizer" onMouseDown={startResize} />
          <div className="right-panel-slot">
            {visiblePanels.length > 1 && (
              <div className="panel-tabs">
                {visiblePanels.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    className={`panel-tab${p.id === activePanel.id ? " panel-tab--active" : ""}`}
                    onClick={() => setActiveTab(p.id)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            )}
            <activePanel.component {...panelProps} />
          </div>
        </>
      )}
    </div>
  );
}
