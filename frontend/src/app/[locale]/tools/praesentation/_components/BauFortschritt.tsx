"use client";

import { useTranslations } from "next-intl";

/** The order the build reports, a step before the current one is behind us whether it ran or was skipped. */
export const BAU_PHASEN = ["texte", "bilder", "bau", "vorschau"] as const;

/** The sheen over the brand circle, white so it carries in both themes. */
const FLUSS_KREIS = {
  backgroundImage: "linear-gradient(90deg, rgba(255,255,255,0) 20%, rgba(255,255,255,0.45) 50%, rgba(255,255,255,0) 80%)",
  backgroundSize: "200% 100%",
  animation: "fluss 1.6s linear infinite",
};

const FLUSS_LINIE = {
  backgroundImage: "linear-gradient(90deg, transparent 20%, var(--kb) 50%, transparent 80%)",
  backgroundSize: "200% 100%",
  animation: "fluss 1.6s linear infinite",
};

const ATEM = { animation: "phase-puls 2.5s ease-in-out infinite" };

interface BauFortschrittProps {
  /** One of BAU_PHASEN, everything else the caller keeps to itself. */
  phase: string;
  detail: string;
}

export default function BauFortschritt({ phase, detail }: BauFortschrittProps) {
  const t = useTranslations("tools.praesentation.slides.phases");
  const jetzt = BAU_PHASEN.indexOf(phase as (typeof BAU_PHASEN)[number]);

  return (
    <div>
      <ol className="flex items-center justify-center gap-1 sm:gap-2">
        {BAU_PHASEN.map((key, i) => {
          const fertig = i < jetzt;
          const laeuft = i === jetzt;
          return (
            <li key={key} className="flex items-center gap-1 sm:gap-2">
              <span className="inline-flex items-center gap-1 sm:gap-1.5 px-1 py-0.5">
                <span
                  aria-current={laeuft ? "step" : undefined}
                  style={laeuft ? FLUSS_KREIS : undefined}
                  className={`
                    inline-flex items-center justify-center w-5 h-5 sm:w-6 sm:h-6 rounded-full text-3xs font-medium flex-shrink-0
                    ${laeuft ? "bg-kb text-white" : ""}
                    ${fertig ? "bg-kb/20 text-kb" : ""}
                    ${!laeuft && !fertig ? "bg-surface text-muted-soft" : ""}
                  `}
                >
                  {fertig ? (
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    i + 1
                  )}
                </span>
                <span
                  style={laeuft ? ATEM : undefined}
                  className={`text-3xs sm:text-xs whitespace-nowrap ${
                    laeuft ? "text-foreground font-medium" : fertig ? "text-muted" : "text-muted-soft"
                  }`}
                >
                  {t(key)}
                </span>
              </span>
              {i < BAU_PHASEN.length - 1 && (
                <span
                  aria-hidden="true"
                  style={laeuft ? FLUSS_LINIE : undefined}
                  className={`w-3 sm:w-8 h-px flex-shrink-0 ${fertig ? "bg-kb" : "bg-surface-dim"}`}
                />
              )}
            </li>
          );
        })}
      </ol>
      <p className="text-sm text-foreground-soft mt-4 text-center">{detail}</p>
    </div>
  );
}
