"use client";

import { useTransition } from "react";

/** Keeps a button marked as busy until the page it navigates to has arrived. */
export function useNavTransition() {
  const [pending, startTransition] = useTransition();
  const navigate = (go: () => void) => startTransition(go);
  return { pending, navigate };
}
