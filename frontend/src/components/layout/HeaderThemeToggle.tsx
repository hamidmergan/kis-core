"use client";

import { useState } from "react";
import { Moon, Sun } from "@phosphor-icons/react";

type Theme = "light" | "dark";

export default function HeaderThemeToggle() {
  const [theme, setTheme] = useState<Theme>("light");
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={isDark ? "Heller Modus" : "Dunkler Modus"}
      title={isDark ? "Heller Modus" : "Dunkler Modus"}
      className="flex items-center justify-center w-9 h-9 rounded-full btn-on-dark"
    >
      {isDark ? (
        <Moon size={17} weight="bold" aria-hidden="true" />
      ) : (
        <Sun size={17} weight="bold" aria-hidden="true" />
      )}
    </button>
  );
}
