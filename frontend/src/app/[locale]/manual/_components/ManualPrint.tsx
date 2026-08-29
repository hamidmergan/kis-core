"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { checkAuthStatus } from "@/lib/auth";
import { Printer } from "@phosphor-icons/react";
import ManualArticleView from "./ManualArticle";
import type { ImageSize } from "../_lib/imageSizes";

type PrintGroup = {
  title: string;
  adminOnly: boolean;
  articles: { slug: string; title: string; markdown: string }[];
};

/** Die ganze Dokumentation am Stueck, mit Inhalt vorweg und Seitenumbruch je Artikel. */
export default function ManualPrintView({
  groups,
  sizes,
}: {
  groups: PrintGroup[];
  sizes: Record<string, ImageSize>;
}) {
  const t = useTranslations("manual");
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    checkAuthStatus().then((s) => setIsAdmin(s.is_admin ?? false));
  }, []);

  // Ohne Adminrecht faellt die Verwaltungs-Gruppe weg, wie im Menue.
  const sichtbar = groups.filter((g) => isAdmin || !g.adminOnly);

  return (
    <div className="relative px-4 sm:px-6 lg:px-8 pt-10 pb-20">
      {/* Kopf und Fuss der Seite gehoeren nicht ins PDF. */}
      <style>{`
        @media print {
          header, footer, .manual-print-hide { display: none !important; }
          .manual-print-break { break-before: page; }
          .manual-print-keep { break-inside: avoid; }
          a { text-decoration: none; color: inherit; }
        }
      `}</style>

      <div className="manual-print-hide absolute top-6 right-4 sm:right-6 lg:right-8">
        <button
          type="button"
          onClick={() => window.print()}
          className="inline-flex items-center gap-2 h-9 px-4 rounded-lg text-sm font-medium btn-primary"
        >
          <Printer size={16} weight="bold" aria-hidden="true" />
          {t("printButton")}
        </button>
      </div>

      <div className="max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold mb-2" style={{ color: "var(--foreground)" }}>
        {t("title")}
      </h1>
      <p className="text-sm mb-10" style={{ color: "var(--muted)" }}>KIS</p>

      <h2 className="text-lg font-semibold mb-3" style={{ color: "var(--foreground)" }}>
        {t("toc")}
      </h2>
      <ol className="mb-4 space-y-3 text-sm">
        {sichtbar.map((group) => (
          <li key={group.title}>
            <span className="font-semibold" style={{ color: "var(--foreground)" }}>{group.title}</span>
            <ul className="mt-1 ml-4 space-y-0.5" style={{ color: "var(--foreground-soft)" }}>
              {group.articles.map((a) => (
                <li key={a.slug}>
                  <a href={`#${a.slug}`}>{a.title}</a>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ol>

      {sichtbar.map((group) => (
        <section key={group.title}>
          <h2
            className="manual-print-break text-2xl font-bold mt-16 mb-8 pb-2"
            style={{ color: "var(--kb-dark)", borderBottom: "2px solid var(--border)" }}
          >
            {group.title}
          </h2>
          {group.articles.map((article) => (
            <div key={article.slug} id={article.slug} className="mb-12">
              <ManualArticleView markdown={article.markdown} sizes={sizes} />
            </div>
          ))}
        </section>
      ))}
      </div>
    </div>
  );
}
