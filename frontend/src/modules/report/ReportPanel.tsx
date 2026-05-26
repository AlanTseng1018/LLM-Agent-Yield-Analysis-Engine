import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import type { PanelModuleProps } from "../registry";
import { isAssistantMessage } from "../../types/chat";
import "./ReportPanel.css";

const API = "";

/** Latest assistant message that produced a report. */
function latestReportId(messages: PanelModuleProps["messages"]): string | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (isAssistantMessage(m) && m.reportId) return m.reportId;
  }
  return null;
}

export function ReportPanel({ messages }: PanelModuleProps) {
  const reportId = latestReportId(messages);
  const [md, setMd] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!reportId) return;
    setMd("");
    setErr("");
    fetch(`${API}/report/${reportId}/files/report.md`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.text();
      })
      // rewrite the report's relative image links to absolute backend URLs
      .then((text) => {
        const base = `${API}/report/${reportId}/files/images/`;
        setMd(
          text
            .replaceAll('src="images/', `src="${base}`)
            .replaceAll("](images/", `](${base}`),
        );
      })
      .catch((e) => setErr(String(e)));
  }, [reportId]);

  return (
    <div className="report-panel">
      <div className="report-panel__header">
        <span>Report</span>
        {reportId && (
          <a className="report-panel__download" href={`${API}/report/${reportId}/download`}>
            ⬇ .zip
          </a>
        )}
      </div>
      <div className="report-panel__body">
        {!reportId ? (
          <div className="report-panel__empty">No report yet — run an analysis.</div>
        ) : err ? (
          <div className="report-panel__empty">Failed to load report: {err}</div>
        ) : md ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
            {md}
          </ReactMarkdown>
        ) : (
          <div className="report-panel__empty">Loading report…</div>
        )}
      </div>
    </div>
  );
}
