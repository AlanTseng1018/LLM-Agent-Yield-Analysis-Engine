import type { ComponentType } from "react";
import type { ChatMessage } from "../types/chat";

// Props passed to every right-panel module by the host App
export type PanelModuleProps = {
  messages: ChatMessage[];
  activeMessageIndex: number | null; // index of the currently-streaming assistant message
  isStreaming: boolean;
};

export type PanelModule = {
  id: string;
  label: string;
  component: ComponentType<PanelModuleProps>;
  /** Return true when this panel should be visible */
  isVisible: (props: PanelModuleProps) => boolean;
};

const registry: PanelModule[] = [];

export function registerPanel(module: PanelModule): void {
  registry.push(module);
}

export function getRegisteredPanels(): PanelModule[] {
  return registry;
}
