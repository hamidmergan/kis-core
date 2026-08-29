import { notFound } from "next/navigation";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import DokuArticleView from "../_components/DokuArticle";
import DokuNav from "../_components/DokuNav";
import { readDokuArticle, readDokuTree } from "../_lib/articles";
import { imageSizes } from "../_lib/imageSizes";

export default async function DokuArticlePage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  const article = readDokuArticle(locale, slug);
  if (!article) notFound();
  const tree = readDokuTree(locale);
  const markdown = article.body.replaceAll("{lang}", locale);

  return (
    <ProtectedRoute>
      <div className="px-4 sm:px-6 lg:px-8 pt-10 pb-20 flex flex-col lg:flex-row gap-8 lg:gap-12">
        <DokuNav tree={tree} activeSlug={slug} />
        <DokuArticleView markdown={markdown} sizes={imageSizes(markdown)} />
      </div>
    </ProtectedRoute>
  );
}
