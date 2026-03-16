import Link from "next/link";

export default function Footer() {
  return (
    <footer
      className="px-6 py-4 text-center text-sm"
      style={{ backgroundColor: "#004261", color: "rgba(255,255,255,0.6)" }}
    >
      <p className="mb-2 text-xs" style={{ color: "rgba(255,255,255,0.5)" }}>
        KIS verwendet KI-Technologie. Alle generierten Inhalte können Fehler enthalten und sollten kritisch geprüft werden.
      </p>
      <Link href="/imprint" className="hover:underline transition-opacity hover:opacity-100 opacity-75">
        Impressum
      </Link>
      <span className="mx-2 opacity-40">|</span>
      <Link href="/privacy" className="hover:underline transition-opacity hover:opacity-100 opacity-75">
        Datenschutz
      </Link>
    </footer>
  );
}
