"use client";

import { useEffect } from "react";
import { useRouter } from "@/i18n/navigation";

/** The landing page moved to the root, old links and printed QR codes still land here. */
export default function InfoRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/");
  }, [router]);
  return null;
}
