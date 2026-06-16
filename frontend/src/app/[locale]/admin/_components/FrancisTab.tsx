"use client";

import Francis from "@/components/ui/Francis";
import MascotShowcase from "./MascotShowcase";

export default function FrancisTab() {
  return <MascotShowcase Component={Francis} namespace="admin.francis" />;
}
