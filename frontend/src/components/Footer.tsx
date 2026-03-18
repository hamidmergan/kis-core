import Link from "next/link";
import Image from "next/image";

export default function Footer({ loggedIn }: { loggedIn?: boolean }) {
  return (
    <footer
      className={`px-6 ${loggedIn ? "pt-8" : "pt-12"} pb-4 text-base`}
      style={{ backgroundColor: "#004261", color: "rgba(255,255,255,0.6)" }}
    >
      <div className="flex flex-col items-center gap-3 text-center">
        {/* KI-Hinweis */}
        {loggedIn && (
          <p className="text-xs max-w-xl opacity-60 leading-relaxed mb-2">
            Diese Plattform nutzt KI und kann Fehler machen. Bitte überprüfen Sie alle Ergebnisse.
          </p>
        )}
        {/* Logos */}
        <div className="flex flex-col sm:flex-row items-center gap-4">
          <a href="https://www.th-luebeck.de" target="_blank" rel="noopener noreferrer" aria-label="TH Lübeck"
            className="flex items-center justify-center w-36 h-14 bg-white opacity-80 hover:opacity-100 transition-opacity px-3">
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
            className="flex items-center justify-center w-36 h-14 bg-white opacity-80 hover:opacity-100 transition-opacity px-3">
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
          <Link href="/imprint" className="hover:underline transition-opacity hover:opacity-100 opacity-75">
            Impressum
          </Link>
          <span className="mx-2 opacity-40">|</span>
          <Link href="/privacy" className="hover:underline transition-opacity hover:opacity-100 opacity-75">
            Datenschutz
          </Link>
        </div>
      </div>
    </footer>
  );
}
