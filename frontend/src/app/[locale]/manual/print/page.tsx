import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ManualPrintView from "../_components/ManualPrint";
import { readManualTree, readManualArticle } from "../_lib/articles";
import { imageSizes, type ImageSize } from "../_lib/imageSizes";

/** Alle Artikel auf einer Seite, gedacht zum Drucken und als PDF sichern. */
export default async function ManualPrintPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const tree = readManualTree(locale);

  const sizes: Record<string, ImageSize> = {};
  const groups = tree.map((group) => ({
    title: group.title,
    adminOnly: group.adminOnly,
    articles: group.articles.map((article) => {
      const markdown = (readManualArticle(locale, article.slug)?.body ?? "").replaceAll("{lang}", locale);
      Object.assign(sizes, imageSizes(markdown));
      return { slug: article.slug, title: article.title, markdown };
    }),
  }));

  return (
    <ProtectedRoute>
      <ManualPrintView groups={groups} sizes={sizes} />
    </ProtectedRoute>
  );
}
