import { notFound } from "next/navigation";
import { redirect } from "@/i18n/navigation";
import { readManualTree, firstSlug } from "./_lib/articles";

export default async function ManualIndexPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const slug = firstSlug(readManualTree(locale));
  if (!slug) notFound();
  redirect({ href: `/manual/${slug}`, locale });
}
