"use client";
import { useEffect } from "react";

export default function FullscreenClass() {
  useEffect(() => {
    const d = document as Document & {
      webkitFullscreenElement?: Element | null;
    };
    const update = () => {
      const fs = !!(document.fullscreenElement || d.webkitFullscreenElement);
      document.body.classList.toggle("has-fullscreen", fs);
    };
    const onBegin = () => document.body.classList.add("has-fullscreen");
    const onEnd = () => document.body.classList.remove("has-fullscreen");

    document.addEventListener("fullscreenchange", update);
    document.addEventListener("webkitfullscreenchange", update);
    document.addEventListener("webkitbeginfullscreen", onBegin, true);
    document.addEventListener("webkitendfullscreen", onEnd, true);

    return () => {
      document.removeEventListener("fullscreenchange", update);
      document.removeEventListener("webkitfullscreenchange", update);
      document.removeEventListener("webkitbeginfullscreen", onBegin, true);
      document.removeEventListener("webkitendfullscreen", onEnd, true);
    };
  }, []);
  return null;
}
