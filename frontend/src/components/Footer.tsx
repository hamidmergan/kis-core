import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-gray-200 bg-white px-6 py-4 text-center text-sm text-gray-500">
      <Link
        href="/impressum"
        className="hover:text-[#0066cc] hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc]"
      >
        Impressum
      </Link>
      <span className="mx-2">|</span>
      <Link
        href="/datenschutz"
        className="hover:text-[#0066cc] hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc]"
      >
        Datenschutz
      </Link>
    </footer>
  );
}
