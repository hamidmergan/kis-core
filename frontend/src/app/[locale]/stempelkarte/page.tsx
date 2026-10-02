"use client";

import { Suspense } from "react";
import StampCard from "./_components/StampCard";

/** The visitor's stamp card, useSearchParams inside needs the boundary. */
export default function StampCardPage() {
  return (
    <Suspense>
      <StampCard />
    </Suspense>
  );
}
