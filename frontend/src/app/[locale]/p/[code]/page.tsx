"use client";

import { useParams } from "next/navigation";
import SharedView from "../../tools/pages/_components/SharedView";

export default function SharedPagePage() {
  const { code } = useParams<{ code: string }>();
  // The view asks for the login itself, only when the owner keeps the link to askFrancis accounts.
  return <SharedView code={code} />;
}
