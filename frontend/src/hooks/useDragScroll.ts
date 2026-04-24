"use client";

import { useEffect, useRef, type RefObject } from "react";

const DRAG_THRESHOLD_PX = 5;

export function useDragScroll(ref: RefObject<HTMLElement | null>) {
  const stateRef = useRef({ active: false, startX: 0, startScroll: 0, moved: 0 });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const onPointerDown = (e: PointerEvent) => {
      if (e.pointerType === "mouse" && e.button !== 0) return;
      stateRef.current = {
        active: true,
        startX: e.clientX,
        startScroll: el.scrollLeft,
        moved: 0,
      };
      el.setPointerCapture(e.pointerId);
    };

    const onPointerMove = (e: PointerEvent) => {
      const s = stateRef.current;
      if (!s.active) return;
      const dx = e.clientX - s.startX;
      s.moved = Math.max(s.moved, Math.abs(dx));
      el.scrollLeft = s.startScroll - dx;
    };

    const endDrag = (e: PointerEvent) => {
      const s = stateRef.current;
      if (!s.active) return;
      s.active = false;
      if (el.hasPointerCapture(e.pointerId)) el.releasePointerCapture(e.pointerId);
    };

    const onClickCapture = (e: MouseEvent) => {
      if (stateRef.current.moved > DRAG_THRESHOLD_PX) {
        e.preventDefault();
        e.stopPropagation();
        stateRef.current.moved = 0;
      }
    };

    el.addEventListener("pointerdown", onPointerDown);
    el.addEventListener("pointermove", onPointerMove);
    el.addEventListener("pointerup", endDrag);
    el.addEventListener("pointercancel", endDrag);
    el.addEventListener("click", onClickCapture, true);

    return () => {
      el.removeEventListener("pointerdown", onPointerDown);
      el.removeEventListener("pointermove", onPointerMove);
      el.removeEventListener("pointerup", endDrag);
      el.removeEventListener("pointercancel", endDrag);
      el.removeEventListener("click", onClickCapture, true);
    };
  }, [ref]);
}
