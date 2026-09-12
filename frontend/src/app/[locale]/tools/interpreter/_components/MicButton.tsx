"use client";

import { Microphone, Stop } from "@phosphor-icons/react";

type Props = {
  recording: boolean;
  disabled?: boolean;
  onClick: () => void;
  startLabel: string;
  stopLabel: string;
  size?: "md" | "lg";
};

/** Round microphone button, red with a pulse while it listens. */
export default function MicButton({ recording, disabled = false, onClick, startLabel, stopLabel, size = "md" }: Props) {
  const box = size === "lg" ? "w-14 h-14" : "w-12 h-12";
  const icon = size === "lg" ? 24 : 20;
  const label = recording ? stopLabel : startLabel;
  return (
    <span className={`relative inline-flex shrink-0 ${box}`}>
      {recording && <span aria-hidden="true" className="absolute inset-0 rounded-full bg-error opacity-25 animate-ping" />}
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        aria-pressed={recording}
        aria-label={label}
        title={label}
        className={`relative ${box} rounded-full flex items-center justify-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${recording ? "btn-danger" : "btn-primary"}`}
      >
        {recording ? <Stop size={icon} weight="fill" /> : <Microphone size={icon} weight="bold" />}
      </button>
    </span>
  );
}
