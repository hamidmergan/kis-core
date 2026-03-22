"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function UploadRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/tools");
  }, [router]);

  return null;
}
