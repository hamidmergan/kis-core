"use client";

import React from "react";
import { MinimizeContext } from "../_context";
import { MiniStrip } from "./MiniStrip";
import type { PanelKey } from "../_types";

interface PanelContext {
  onMinimize: () => void;
  hideHeader: boolean;
}

interface WorkspacePanelsLayoutProps {
  // Mobile / Desktop
  isMobile: boolean;
  activeTab: PanelKey;
  setActiveTab: (k: PanelKey) => void;
  // Panels state & refs
  panels: Record<PanelKey, boolean>;
  togglePanel: (k: PanelKey) => void;
  panelContainerRef: React.RefObject<HTMLDivElement | null>;
  p1Ref: React.RefObject<HTMLDivElement | null>;
  p2Ref: React.RefObject<HTMLDivElement | null>;
  p3Ref: React.RefObject<HTMLDivElement | null>;
  p1Style: React.CSSProperties;
  p2Style: React.CSSProperties;
  p3Style: React.CSSProperties;
  studioEnabled: boolean;
  canDrag: boolean;
  startDrag: (which: 1 | 2, e: React.MouseEvent) => void;
  // Render slots
  renderQuellen: (ctx: PanelContext) => React.ReactNode;
  renderChat: (ctx: PanelContext) => React.ReactNode;
  renderStudio: (ctx: PanelContext) => React.ReactNode;
}

const panelBaseClass = "flex flex-col overflow-hidden rounded-2xl";
const panelBaseStyle = { backgroundColor: "var(--surface)", boxShadow: "0 1px 4px rgba(0,0,0,0.07)" };

export function WorkspacePanelsLayout(props: WorkspacePanelsLayoutProps) {
  const {
    isMobile, activeTab, setActiveTab,
    panels, togglePanel, panelContainerRef,
    p1Ref, p2Ref, p3Ref,
    p1Style, p2Style, p3Style,
    studioEnabled, canDrag, startDrag,
    renderQuellen, renderChat, renderStudio,
  } = props;

  if (isMobile) {
    const switchToChat = () => setActiveTab("chat");
    return (
      <div
        ref={panelContainerRef}
        className="flex flex-1 overflow-hidden mobile-flow"
        style={{ padding: 8, gap: 0, backgroundColor: "var(--bg)" }}
      >
        <MinimizeContext.Provider value={switchToChat}>
          <div
            className="flex flex-col flex-1 overflow-hidden rounded-2xl mobile-flow mobile-center"
            style={panelBaseStyle}
          >
            {activeTab === "quellen"
              ? renderQuellen({ onMinimize: switchToChat, hideHeader: true })
              : activeTab === "chat"
                ? renderChat({ onMinimize: switchToChat, hideHeader: true })
                : renderStudio({ onMinimize: switchToChat, hideHeader: true })}
          </div>
        </MinimizeContext.Provider>
      </div>
    );
  }

  return (
    <div
      ref={panelContainerRef}
      className="flex flex-1 overflow-hidden mobile-flow"
      style={{ padding: 8, gap: 0, backgroundColor: "var(--bg)" }}
    >
      <div ref={p1Ref} className={panelBaseClass} style={{ ...p1Style, ...panelBaseStyle }}>
        {!panels.quellen
          ? <MiniStrip label="Quellen" onClick={() => togglePanel("quellen")} side="left" />
          : renderQuellen({ onMinimize: () => togglePanel("quellen"), hideHeader: false })}
      </div>

      <DragHandle canDrag={canDrag} onMouseDown={(e) => canDrag && startDrag(1, e)} />

      <div ref={p2Ref} className={panelBaseClass} style={{ ...p2Style, ...panelBaseStyle }}>
        {!panels.chat
          ? <MiniStrip label="Chat" onClick={() => togglePanel("chat")} side="left" />
          : renderChat({ onMinimize: () => togglePanel("chat"), hideHeader: false })}
      </div>

      {studioEnabled && (
        <>
          <DragHandle canDrag={canDrag} onMouseDown={(e) => canDrag && startDrag(2, e)} />
          <div ref={p3Ref} className={panelBaseClass} style={{ ...p3Style, ...panelBaseStyle }}>
            <MinimizeContext.Provider value={() => togglePanel("studio")}>
              {!panels.studio
                ? <MiniStrip label="Studio" onClick={() => togglePanel("studio")} side="right" />
                : renderStudio({ onMinimize: () => togglePanel("studio"), hideHeader: false })}
            </MinimizeContext.Provider>
          </div>
        </>
      )}
    </div>
  );
}

function DragHandle({ canDrag, onMouseDown }: { canDrag: boolean; onMouseDown: (e: React.MouseEvent) => void }) {
  return (
    <div
      className="group flex-shrink-0 flex items-center justify-center"
      style={{ width: 8, cursor: canDrag ? "col-resize" : "default" }}
      onMouseDown={onMouseDown}
    >
      <div
        className="w-0.5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
        style={{ height: 48, backgroundColor: "var(--kb)" }}
      />
    </div>
  );
}
