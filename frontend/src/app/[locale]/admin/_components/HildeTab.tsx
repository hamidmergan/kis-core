"use client";

import Hilde from "@/components/ui/Hilde";
import MascotShowcase from "./MascotShowcase";

export default function HildeTab() {
  return <MascotShowcase Component={Hilde} namespace="admin.hilde" />;
}
