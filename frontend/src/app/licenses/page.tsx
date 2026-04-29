import fs from "fs";
import path from "path";

export const metadata = {
  title: "Open-Source-Lizenzen",
};

export default function LicensesPage() {
  const noticeFile = path.join(process.cwd(), "public", "THIRD-PARTY-NOTICES.txt");
  const notice = fs.readFileSync(noticeFile, "utf-8");

  return (
    <div className="max-w-4xl mx-auto px-4 py-10">
      <div className="bg-white rounded-xl shadow-sm border border-border-soft p-8">
        <h1 className="text-2xl font-bold mb-6">Open-Source-Lizenzen</h1>

        <p className="text-foreground-soft mb-4">
          KIS ist Open Source unter der{" "}
          <a
            href="https://www.apache.org/licenses/LICENSE-2.0"
            target="_blank"
            rel="noopener noreferrer"
            className="underline"
          >
            Apache License 2.0
          </a>
          , Copyright 2026 Technische Hochschule Lübeck.
        </p>

        <p className="text-foreground-soft mb-4">
          Die Plattform nutzt eine Reihe von Open-Source-Bibliotheken (Backend in
          Python, Frontend in JavaScript/TypeScript). Die folgende Liste enthält
          alle direkten und transitiven Abhängigkeiten samt Lizenz und vollem
          Lizenztext.
        </p>

        <p className="text-foreground-soft mb-4">
          Hinweis zu schwachem Copyleft: Backend nutzt{" "}
          <code className="text-sm bg-gray-100 px-1 rounded">ldap3</code> (LGPLv3)
          und <code className="text-sm bg-gray-100 px-1 rounded">psycopg2-binary</code>{" "}
          (LGPL). Beide werden unverändert via PyPI als dynamisch geladene
          Bibliotheken eingebunden, was die LGPL-Pflichten erfüllt. Quellcode der
          Bibliotheken: siehe Links in der unten stehenden Liste.
        </p>

        <p className="text-foreground-soft mb-6">
          Maschinenlesbar als{" "}
          <a
            href="/THIRD-PARTY-NOTICES.txt"
            target="_blank"
            rel="noopener noreferrer"
            className="underline"
          >
            THIRD-PARTY-NOTICES.txt
          </a>
          .
        </p>

        <pre className="text-xs bg-gray-50 border border-border-soft rounded p-4 overflow-auto whitespace-pre-wrap font-mono leading-relaxed max-h-[70vh]">
          {notice}
        </pre>
      </div>
    </div>
  );
}
