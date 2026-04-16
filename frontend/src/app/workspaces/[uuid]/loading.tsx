import Header from "@/components/layout/Header";

function SkeletonBlock({ className = "", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <div
      className={`rounded-md animate-pulse ${className}`}
      style={{ backgroundColor: "var(--surface-dim)", ...style }}
    />
  );
}

function SourcesSkeleton() {
  return (
    <div className="flex-1 flex flex-col overflow-hidden" style={{ minWidth: 200 }}>
      <div className="flex items-center justify-between px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
        <SkeletonBlock className="h-4 w-20" />
        <SkeletonBlock className="h-7 w-7 rounded-full" />
      </div>
      <div className="flex-1 p-3 flex flex-col gap-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="flex items-center gap-3 p-2 rounded-lg">
            <SkeletonBlock className="h-8 w-8 flex-shrink-0" />
            <div className="flex-1 flex flex-col gap-1.5 min-w-0">
              <SkeletonBlock className="h-3" style={{ width: `${60 + i * 8}%` }} />
              <SkeletonBlock className="h-2.5 w-1/3" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ChatSkeleton() {
  return (
    <div className="flex-1 flex flex-col overflow-hidden" style={{ minWidth: 200 }}>
      <div className="flex items-center justify-between px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
        <SkeletonBlock className="h-4 w-16" />
        <SkeletonBlock className="h-7 w-7 rounded-full" />
      </div>
      <div className="flex-1 p-4 flex flex-col gap-4">
        <div className="flex flex-col gap-2 self-start max-w-[80%] w-full">
          <SkeletonBlock className="h-3 w-full" />
          <SkeletonBlock className="h-3 w-5/6" />
          <SkeletonBlock className="h-3 w-3/4" />
        </div>
        <div className="flex flex-col gap-2 self-end max-w-[70%] w-full items-end">
          <SkeletonBlock className="h-3 w-3/4" />
          <SkeletonBlock className="h-3 w-2/3" />
        </div>
      </div>
      <div className="p-4 flex-shrink-0" style={{ borderTop: "1px solid var(--border)" }}>
        <SkeletonBlock className="h-11 w-full rounded-xl" />
      </div>
    </div>
  );
}

function StudioSkeleton() {
  return (
    <div className="flex-1 flex flex-col overflow-hidden" style={{ minWidth: 200 }}>
      <div className="flex items-center justify-between px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
        <SkeletonBlock className="h-4 w-16" />
        <SkeletonBlock className="h-7 w-7 rounded-full" />
      </div>
      <div className="flex gap-4 px-4 py-2 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
        {[0, 1, 2, 3].map((i) => (
          <SkeletonBlock key={i} className="h-3 w-14" />
        ))}
      </div>
      <div className="p-3 flex-shrink-0">
        <SkeletonBlock className="h-2.5 w-20 mb-2" />
        <div className="grid grid-cols-2 gap-2">
          {[0, 1, 2, 3].map((i) => (
            <SkeletonBlock key={i} className="h-16" />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function Loading() {
  return (
    <div className="flex flex-col overflow-hidden" style={{ height: "100vh" }}>
      <Header showLogout />

      {/* Topbar (desktop) */}
      <div
        className="hidden md:flex items-center px-5 flex-shrink-0"
        style={{ height: 48 }}
      >
        <SkeletonBlock className="h-3 w-36" />
        <div className="ml-auto">
          <SkeletonBlock className="h-7 w-7 rounded-full" />
        </div>
      </div>

      {/* Desktop: 3-panel skeleton */}
      <div className="hidden md:flex flex-1 overflow-hidden">
        <SourcesSkeleton />
        <div style={{ width: 1, backgroundColor: "var(--border)" }} />
        <ChatSkeleton />
        <div style={{ width: 1, backgroundColor: "var(--border)" }} />
        <StudioSkeleton />
      </div>

      {/* Mobile: tabs + single pane */}
      <div className="md:hidden flex flex-col flex-1 overflow-hidden">
        <div className="flex gap-1 px-3 py-2 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
          {[0, 1, 2].map((i) => (
            <SkeletonBlock key={i} className="h-8 flex-1" />
          ))}
        </div>
        <ChatSkeleton />
      </div>
    </div>
  );
}
