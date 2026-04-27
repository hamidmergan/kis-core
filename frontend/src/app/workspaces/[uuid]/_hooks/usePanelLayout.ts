"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { _isMediaFile } from "../_utils";
import type { PanelKey, ViewerState } from "../_types";

const MIN_PANEL = 50;
const MOBILE_BREAKPOINT = 768;

// Smartphones get the single-panel layout regardless of viewport dimensions
// (landscape iPhones can be 844x390 — neither max-width:767 nor every browser's
// pointer:coarse query catches that reliably). UA hints + UA-string fallback
// cover real devices across iOS/Android/browsers. Tablets in portrait fall
// into single-panel via the mediaQuery below; landscape keeps 3 panels.
function isPhoneUA(): boolean {
  if (typeof navigator === "undefined") return false;
  const uaData = (navigator as { userAgentData?: { mobile?: boolean } }).userAgentData;
  if (uaData?.mobile === true) return true;
  const ua = navigator.userAgent || "";
  if (/iPhone|iPod|BlackBerry|webOS|Windows Phone|IEMobile|Opera Mini/i.test(ua)) return true;
  return /Android/i.test(ua) && /Mobile/i.test(ua);
}

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
  const [isPhone] = useState<boolean>(() => isPhoneUA());
  const [isMobile, setIsMobile] = useState<boolean>(() => isPhoneUA());
  const [isLandscape, setIsLandscape] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia("(orientation: landscape)").matches;
  });
  const isPhoneLandscape = isPhone && isLandscape;
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

  // Tablet-portrait (iPad etc.) bekommt ebenfalls Single-Panel — bei 768-1024px
  // breit ist 3-Panel-Layout zu eng. Bei orientation:landscape wechselt das
  // Tablet zurück auf 3 Panels (matchMedia-Listener feuert auf Rotation).
  const mobileMediaQuery = `(max-width: ${MOBILE_BREAKPOINT - 1}px), (max-height: 500px) and (pointer: coarse), (orientation: portrait) and (pointer: coarse) and (max-width: 1024px)`;

  useEffect(() => {
    const mq = window.matchMedia(mobileMediaQuery);
    const computed = isPhone || mq.matches;
    setIsMobile(computed);
    if (computed) setActiveTab("quellen");
    if (isPhone) return; // UA can't change at runtime — no listener needed
    const handler = (e: MediaQueryListEvent) => {
      if (mediaOpenRef.current) return;
      setIsMobile(e.matches);
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [isPhone, mobileMediaQuery]);

  useEffect(() => {
    if (mediaOpen) return;
    setIsMobile(isPhone || window.matchMedia(mobileMediaQuery).matches);
  }, [isPhone, mediaOpen, mobileMediaQuery]);

  // Track orientation only on phones — drives is-phone-landscape body class
  // so CSS rules that hide header/title and narrow the panel fire on phones
  // in landscape regardless of pointer:coarse / viewport-height quirks.
  useEffect(() => {
    if (!isPhone) return;
    const mq = window.matchMedia("(orientation: landscape)");
    setIsLandscape(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsLandscape(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [isPhone]);

  useEffect(() => {
    if (typeof document === "undefined") return;
    document.body.classList.toggle("is-phone-landscape", isPhoneLandscape);
    return () => { document.body.classList.remove("is-phone-landscape"); };
  }, [isPhoneLandscape]);

  const togglePanel = useCallback((key: PanelKey) => {
    setPanels((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      if (Object.values(next).every((v) => !v)) return prev;
      return next;
    });
  }, []);

  const startDrag = useCallback((divider: 1 | 2, e: React.PointerEvent) => {
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
    const pointerId = e.pointerId;
    const target = e.currentTarget as HTMLElement;
    try { target.setPointerCapture(pointerId); } catch { /* ignore */ }

    function clampDelta(raw: number) {
      return Math.min(startB - MIN_PANEL, Math.max(-(startA - MIN_PANEL), raw));
    }

    function onMove(ev: PointerEvent) {
      if (ev.pointerId !== pointerId) return;
      if (!refA.current || !refB.current) return;
      const d = clampDelta(ev.clientX - startX);
      refA.current.style.flexBasis = `${startA + d}px`;
      refB.current.style.flexBasis = `${startB - d}px`;
    }

    function cleanup() {
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
      document.removeEventListener("pointercancel", onCancel);
      try { target.releasePointerCapture(pointerId); } catch { /* ignore */ }
    }

    function onUp(ev: PointerEvent) {
      if (ev.pointerId !== pointerId) return;
      cleanup();
      const d = clampDelta(ev.clientX - startX);
      const setA = keyA === "p1" ? setP1Width : keyA === "p2" ? setP2Width : setP3Width;
      const setB = keyB === "p1" ? setP1Width : keyB === "p2" ? setP2Width : setP3Width;
      setA(startA + d);
      setB(startB - d);
    }

    function onCancel(ev: PointerEvent) {
      if (ev.pointerId !== pointerId) return;
      cleanup();
    }

    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
    document.addEventListener("pointercancel", onCancel);
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
