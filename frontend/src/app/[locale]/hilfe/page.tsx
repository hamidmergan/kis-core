import { notFound } from "next/navigation";
import { redirect } from "@/i18n/navigation";
import { readHelpTree, firstSlug } from "./_lib/articles";

export default async function HelpIndexPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const slug = firstSlug(readHelpTree(locale));
  if (!slug) notFound();
  redirect({ href: `/hilfe/${slug}`, locale });
}
