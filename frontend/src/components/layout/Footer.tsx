import Link from "next/link";
import Image from "next/image";

export default function Footer({ loggedIn }: { loggedIn?: boolean }) {
  return (
    <footer
      className={`px-6 ${loggedIn ? "pt-8" : "pt-12"} pb-4 text-base`}
      style={{ backgroundColor: "var(--header-bg)", color: "rgba(255,255,255,0.6)", borderTop: "1px solid var(--border)" }}
    >
      <div className="flex flex-col items-center gap-3 text-center">
        {/* AI notice */}
        {loggedIn && (
          <div className="w-full text-xs leading-relaxed mb-2 flex flex-col gap-1">
            <p className="w-full">Diese Plattform nutzt KI und kann Fehler machen. Überprüfen Sie die Antworten.</p>
            <p className="w-full">
              Feedback oder Probleme?{" "}
              <a href="mailto:hamid.mergan@th-luebeck.de" className="link-footer">
                hamid.mergan@th-luebeck.de
              </a>
            </p>
          </div>
        )}
        {/* Logos */}
        <div className="flex flex-col sm:flex-row items-center gap-4">
          <a href="https://www.th-luebeck.de" target="_blank" rel="noopener noreferrer" aria-label="TH Lübeck"
            className="flex items-center justify-center w-36 h-14 bg-white logo-link px-3">
            <Image
              src="/logos/logo-thl.jpg"
              alt="TH Lübeck"
              width={110}
              height={44}
              className="object-contain max-h-10"
              style={{ width: "auto" }}
            />
          </a>
          <a href="https://www.th-luebeck.de/isy/" target="_blank" rel="noopener noreferrer" aria-label="ISY"
            className="flex items-center justify-center w-36 h-14 bg-white logo-link px-3">
            <Image
              src="/logos/isy-logo.png"
              alt="ISY"
              width={80}
              height={44}
              className="object-contain max-h-10"
              style={{ width: "auto" }}
            />
          </a>
        </div>

        {/* Links */}
        <div className="text-sm">
          <Link href="/imprint" className="link-footer">
            Impressum
          </Link>
          <span className="mx-2 opacity-40">|</span>
          <Link href="/privacy" className="link-footer">
            Datenschutz
          </Link>
        </div>
      </div>
    </footer>
  );
}
