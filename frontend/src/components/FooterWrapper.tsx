"use client";

import { usePathname } from "next/navigation";
import Footer from "./Footer";

const GUEST_PATHS = ["/login", "/pending"];

export default function FooterWrapper() {
  const pathname = usePathname();
  const loggedIn = !GUEST_PATHS.includes(pathname);
  return <Footer loggedIn={loggedIn} />;
}
