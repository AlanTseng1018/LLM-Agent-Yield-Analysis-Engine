import { registerPanel } from "../registry";
import { ReportPanel } from "./ReportPanel";
import { isAssistantMessage } from "../../types/chat";

registerPanel({
  id: "report",
  label: "Report",
  component: ReportPanel,
  // visible once any assistant message has produced a report
  isVisible: ({ messages }) =>
    messages.some((m) => isAssistantMessage(m) && !!m.reportId),
});
