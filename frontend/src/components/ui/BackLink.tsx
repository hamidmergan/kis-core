import Link from "next/link";

export default function BackLink() {
  return (
    <Link
      href="/tools"
      className="inline-flex items-center gap-1.5 text-sm font-medium mb-6 transition-colors group"
      style={{ color: "var(--kb)" }}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className="transition-transform group-hover:-translate-x-0.5"
      >
        <path d="M19 12H5M12 5l-7 7 7 7" />
      </svg>
      Zur Übersicht
    </Link>
  );
}
