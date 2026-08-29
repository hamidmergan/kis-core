import { notFound } from "next/navigation";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import HelpArticleView from "../_components/HelpArticle";
import HelpNav from "../_components/HelpNav";
import { readHelpArticle, readHelpTree } from "../_lib/articles";
import { imageSizes } from "../_lib/imageSizes";

export default async function HelpArticlePage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  const article = readHelpArticle(locale, slug);
  if (!article) notFound();
  const tree = readHelpTree(locale);
  const markdown = article.body.replaceAll("{lang}", locale);

  return (
    <ProtectedRoute>
      <div className="px-4 sm:px-6 lg:px-8 pt-10 pb-20 flex flex-col lg:flex-row gap-8 lg:gap-12">
        <HelpNav tree={tree} activeSlug={slug} />
        <HelpArticleView markdown={markdown} sizes={imageSizes(markdown)} />
      </div>
    </ProtectedRoute>
  );
}
