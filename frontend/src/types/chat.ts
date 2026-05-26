import type { Message } from "./message";

export type AssistantMessage = Message & {
  role: "assistant";
  thinkingText?: string;   // raw accumulated thinking text (source of truth for thinking panel)
  thinkingDone?: boolean;  // true once stream is complete
  images?: { url: string; label: string; analysis: string }[];
  postContent?: string;    // text rendered AFTER the image grid (e.g. batch PIN analysis)
  reportId?: string;       // id of the generated report folder, enables the download button
};

export type ChatMessage = Message | AssistantMessage;

export function isAssistantMessage(m: ChatMessage): m is AssistantMessage {
  return m.role === "assistant";
}
