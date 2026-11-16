import { useEffect, useLayoutEffect, useRef, useState } from "react";

/** A menu on document.body that hangs below its trigger and closes on a click outside. */
export function useAnchoredMenu(menuWidth: number, gap: number) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      const target = e.target as Node;
      if (triggerRef.current?.contains(target)) return;
      if (menuRef.current?.contains(target)) return;
      setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  useLayoutEffect(() => {
    if (!open) return;
    function update() {
      const btn = triggerRef.current?.getBoundingClientRect();
      if (!btn) return;
      const left = Math.min(btn.right - menuWidth, window.innerWidth - menuWidth - 8);
      setPos({ top: btn.bottom + gap, left: Math.max(8, left) });
    }
    update();
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [open, menuWidth, gap]);

  return { open, setOpen, pos, triggerRef, menuRef };
}
