import { notFound } from "next/navigation";
import { redirect } from "@/i18n/navigation";
import { readDokuTree, firstSlug } from "./_lib/articles";

export default async function DokuIndexPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const slug = firstSlug(readDokuTree(locale));
  if (!slug) notFound();
  redirect({ href: `/doku/${slug}`, locale });
}
