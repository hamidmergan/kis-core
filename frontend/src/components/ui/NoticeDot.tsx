/** Small red dot that marks something still waiting, with a text for screen readers. */
export default function NoticeDot({ label, className = "" }: { label: string; className?: string }) {
  return (
    <>
      <span className={`w-1.5 h-1.5 bg-error rounded-full shadow shrink-0 ${className}`} aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </>
  );
}
