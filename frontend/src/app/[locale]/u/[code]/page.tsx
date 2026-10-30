"use client";

import { useParams } from "next/navigation";
import CollectionView from "../../tools/pages/_components/CollectionView";

export default function CollectionPage() {
  const { code } = useParams<{ code: string }>();
  // The view asks for the login itself, only when the owner keeps the link to ASK Francis accounts.
  return <CollectionView code={code} />;
}
