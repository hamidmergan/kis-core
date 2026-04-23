"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { _isMediaFile } from "../_utils";
import type { PanelKey, ViewerState } from "../_types";

const MIN_PANEL = 50;
const MOBILE_BREAKPOINT = 768;

interface UsePanelLayoutOptions {
  uuid: string;
  viewerSource: ViewerState | null;
}

export function usePanelLayout({ uuid, viewerSource }: UsePanelLayoutOptions) {
  const [panels, setPanels] = useState<Record<PanelKey, boolean>>(() => {
    if (typeof window === "undefined") return { quellen: true, chat: true, studio: true };
    try {
      const stored = localStorage.getItem(`ki-assistent-panels-${uuid}`);
      if (stored) return JSON.parse(stored);
    } catch { /* ignore */ }
    return { quellen: true, chat: true, studio: true };
  });
  const [p1Width, setP1Width] = useState(360);
  const [p2Width, setP2Width] = useState(500);
  const [p3Width, setP3Width] = useState(380);
  const [activeTab, setActiveTab] = useState<PanelKey>("chat");
  const [isMobile, setIsMobile] = useState(false);
  const [hideHeader, setHideHeader] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    try { return localStorage.getItem(`ki-assistent-hide-header-${uuid}`) === "1"; } catch { return false; }
  });

  const panelContainerRef = useRef<HTMLDivElement>(null);
  const p1Ref = useRef<HTMLDivElement>(null);
  const p2Ref = useRef<HTMLDivElement>(null);
  const p3Ref = useRef<HTMLDivElement>(null);
  const panelsRef = useRef(panels);
  panelsRef.current = panels;

  // Persist hideHeader
  useEffect(() => {
    try { localStorage.setItem(`ki-assistent-hide-header-${uuid}`, hideHeader ? "1" : "0"); } catch { /* ignore */ }
  }, [hideHeader, uuid]);

  // Persist panels
  useEffect(() => {
    try { localStorage.setItem(`ki-assistent-panels-${uuid}`, JSON.stringify(panels)); } catch { /* ignore */ }
  }, [panels, uuid]);

  // Mobile detection — treat phone-landscape as mobile too
  const mediaOpen = viewerSource !== null && _isMediaFile(viewerSource.filename);
  const mediaOpenRef = useRef(mediaOpen);
  mediaOpenRef.current = mediaOpen;

  const mobileMediaQuery = `(max-width: ${MOBILE_BREAKPOINT - 1}px), (max-height: 500px) and (pointer: coarse)`;

  useEffect(() => {
    const mq = window.matchMedia(mobileMediaQuery);
    setIsMobile(mq.matches);
    if (mq.matches) setActiveTab("quellen");
    const handler = (e: MediaQueryListEvent) => {
      if (mediaOpenRef.current) return;
      setIsMobile(e.matches);
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [mobileMediaQuery]);

  useEffect(() => {
    if (!mediaOpen) {
      setIsMobile(window.matchMedia(mobileMediaQuery).matches);
    }
  }, [mediaOpen, mobileMediaQuery]);

  const togglePanel = useCallback((key: PanelKey) => {
    setPanels((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      if (Object.values(next).every((v) => !v)) return prev;
      return next;
    });
  }, []);

  const startDrag = useCallback((divider: 1 | 2, e: React.MouseEvent) => {
    e.preventDefault();
    const p = panelsRef.current;

    const panelKeys: PanelKey[] = ["quellen", "chat", "studio"];
    const refs = [p1Ref, p2Ref, p3Ref];
    const keys = ["p1", "p2", "p3"] as const;

    const openIdxs = [0, 1, 2].filter((i) => p[panelKeys[i]]);
    if (openIdxs.length < 2) return;

    const idx = divider === 1 ? 1 : 2;
    let leftIdx: number, rightIdx: number;
    const directLeft = openIdxs.filter((i) => i < idx);
    const directRight = openIdxs.filter((i) => i >= idx);
    if (directLeft.length > 0 && directRight.length > 0) {
      leftIdx = directLeft[directLeft.length - 1];
      rightIdx = directRight[0];
    } else {
      leftIdx = openIdxs[0];
      rightIdx = openIdxs[1];
    }

    const refA = refs[leftIdx], refB = refs[rightIdx];
    const keyA = keys[leftIdx], keyB = keys[rightIdx];

    const widths = { p1: p1Width, p2: p2Width, p3: p3Width };
    const startX = e.clientX;
    const startA = widths[keyA];
    const startB = widths[keyB];

    function clampDelta(raw: number) {
      return Math.min(startB - MIN_PANEL, Math.max(-(startA - MIN_PANEL), raw));
    }

    function onMove(ev: MouseEvent) {
      if (!refA.current || !refB.current) return;
      const d = clampDelta(ev.clientX - startX);
      refA.current.style.flexBasis = `${startA + d}px`;
      refB.current.style.flexBasis = `${startB - d}px`;
    }

    function onUp(ev: MouseEvent) {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      const d = clampDelta(ev.clientX - startX);
      const setA = keyA === "p1" ? setP1Width : keyA === "p2" ? setP2Width : setP3Width;
      const setB = keyB === "p1" ? setP1Width : keyB === "p2" ? setP2Width : setP3Width;
      setA(startA + d);
      setB(startB - d);
    }

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, [p1Width, p2Width, p3Width]);

  return {
    panels, setPanels,
    p1Width, p2Width, p3Width,
    activeTab, setActiveTab,
    isMobile,
    hideHeader, setHideHeader,
    panelContainerRef, p1Ref, p2Ref, p3Ref,
    togglePanel, startDrag,
  };
}
