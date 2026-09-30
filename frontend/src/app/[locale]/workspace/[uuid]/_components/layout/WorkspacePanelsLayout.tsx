"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { MinimizeContext } from "../../_context";
import { MiniStrip } from "./MiniStrip";
import type { PanelKey } from "../../_types";

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
  focusPanel: (k: PanelKey, visible: PanelKey[]) => void;
  panelContainerRef: React.RefObject<HTMLDivElement | null>;
  p1Ref: React.RefObject<HTMLDivElement | null>;
  p2Ref: React.RefObject<HTMLDivElement | null>;
  p3Ref: React.RefObject<HTMLDivElement | null>;
  p1Style: React.CSSProperties;
  p2Style: React.CSSProperties;
  p3Style: React.CSSProperties;
  studioEnabled: boolean;
  canDrag: boolean;
  startDrag: (which: 1 | 2, e: React.PointerEvent) => void;
  // Render slots
  renderQuellen: (ctx: PanelContext) => React.ReactNode;
  renderChat: (ctx: PanelContext) => React.ReactNode;
  renderStudio: (ctx: PanelContext) => React.ReactNode;
  // Locks sources & studio mini-strips while diagnosis runs in middle slot
  diagnosisActive?: boolean;
}

const panelBaseClass = "flex flex-col overflow-hidden rounded-2xl";
const panelBaseStyle = { backgroundColor: "var(--surface)", boxShadow: "0 1px 4px rgba(0,0,0,0.07)" };

// Only a double click on the header itself counts, never on a button or field inside it.
function hitsPanelHeader(target: EventTarget): boolean {
  if (!(target instanceof Element)) return false;
  if (!target.closest("[data-panel-header]")) return false;
  return !target.closest("button, a, input, textarea, select, [role='button'], [contenteditable='true']");
}

export function WorkspacePanelsLayout(props: WorkspacePanelsLayoutProps) {
  const {
    isMobile, activeTab, setActiveTab,
    panels, togglePanel, focusPanel, panelContainerRef,
    p1Ref, p2Ref, p3Ref,
    p1Style, p2Style, p3Style,
    studioEnabled, canDrag, startDrag,
    renderQuellen, renderChat, renderStudio,
    diagnosisActive = false,
  } = props;
  const tPanels = useTranslations("workspace.detail.panels");
  const tDiag = useTranslations("workspace.detail.languageTraining.diagnosis");
  const diagnosisLockTooltip = tDiag("panelDisabledTooltip");

  if (isMobile) {
    const switchToChat = () => setActiveTab("chat");
    // All three panels stay mounted and are only switched invisible.
    const layerStyle = (key: PanelKey): React.CSSProperties => {
      const active = activeTab === key;
      return {
        position: "absolute",
        inset: 8,
        visibility: active ? "visible" : "hidden",
        pointerEvents: active ? "auto" : "none",
        zIndex: active ? 1 : 0,
      };
    };
    return (
      <div
        ref={panelContainerRef}
        className="flex flex-1 overflow-hidden"
        style={{ position: "relative", backgroundColor: "var(--background)" }}
      >
        <MinimizeContext.Provider value={switchToChat}>
          <div
            className="flex flex-col overflow-hidden rounded-2xl"
            style={{ ...panelBaseStyle, ...layerStyle("quellen") }}
          >
            {renderQuellen({ onMinimize: switchToChat, hideHeader: true })}
          </div>
          <div
            className="flex flex-col overflow-hidden rounded-2xl"
            style={{ ...panelBaseStyle, ...layerStyle("chat") }}
          >
            {renderChat({ onMinimize: switchToChat, hideHeader: true })}
          </div>
          <div
            className="flex flex-col overflow-hidden rounded-2xl"
            style={{ ...panelBaseStyle, ...layerStyle("studio") }}
          >
            {renderStudio({ onMinimize: switchToChat, hideHeader: true })}
          </div>
        </MinimizeContext.Provider>
      </div>
    );
  }

  // Like a window title bar: the double-clicked panel stays, the others shrink to their strip.
  const visiblePanels: PanelKey[] = studioEnabled ? ["quellen", "chat", "studio"] : ["quellen", "chat"];
  const headerHandlers = (key: PanelKey) => ({
    onMouseDown: (e: React.MouseEvent) => {
      // Keeps the second click from selecting the title word.
      if (e.detail > 1 && hitsPanelHeader(e.target)) e.preventDefault();
    },
    onDoubleClick: (e: React.MouseEvent) => {
      if (hitsPanelHeader(e.target)) focusPanel(key, visiblePanels);
    },
  });

  return (
    <div
      ref={panelContainerRef}
      className="flex flex-1 overflow-hidden"
      style={{ padding: 8, gap: 0, backgroundColor: "var(--background)" }}
    >
      <div ref={p1Ref} className={panelBaseClass} style={{ ...p1Style, ...panelBaseStyle }} {...headerHandlers("quellen")}>
        {!panels.quellen
          ? <MiniStrip
              label={tPanels("sources")}
              onClick={() => togglePanel("quellen")}
              side="left"
              disabled={diagnosisActive}
              disabledTooltip={diagnosisLockTooltip}
            />
          : renderQuellen({ onMinimize: () => togglePanel("quellen"), hideHeader: false })}
      </div>

      <DragHandle canDrag={canDrag} onPointerDown={(e) => canDrag && startDrag(1, e)} />

      <div ref={p2Ref} className={panelBaseClass} style={{ ...p2Style, ...panelBaseStyle }} {...headerHandlers("chat")}>
        {!panels.chat
          ? <MiniStrip label={tPanels("chat")} onClick={() => togglePanel("chat")} side="left" />
          : renderChat({ onMinimize: () => togglePanel("chat"), hideHeader: false })}
      </div>

      {studioEnabled && (
        <>
          <DragHandle canDrag={canDrag} onPointerDown={(e) => canDrag && startDrag(2, e)} />
          <div ref={p3Ref} className={panelBaseClass} style={{ ...p3Style, ...panelBaseStyle }} {...headerHandlers("studio")}>
            <MinimizeContext.Provider value={() => togglePanel("studio")}>
              {!panels.studio
                ? <MiniStrip
                    label={tPanels("studio")}
                    onClick={() => togglePanel("studio")}
                    side="right"
                    disabled={diagnosisActive}
                    disabledTooltip={diagnosisLockTooltip}
                  />
                : renderStudio({ onMinimize: () => togglePanel("studio"), hideHeader: false })}
            </MinimizeContext.Provider>
          </div>
        </>
      )}
    </div>
  );
}

function DragHandle({ canDrag, onPointerDown }: { canDrag: boolean; onPointerDown: (e: React.PointerEvent) => void }) {
  return (
    <div
      className="panel-drag-handle flex-shrink-0 flex items-center justify-center"
      style={{ cursor: canDrag ? "col-resize" : "default", touchAction: "none" }}
      onPointerDown={onPointerDown}
    >
      <div
        className="panel-drag-handle-bar rounded-full transition-opacity"
        style={{ backgroundColor: "var(--kb)" }}
      />
    </div>
  );
}
