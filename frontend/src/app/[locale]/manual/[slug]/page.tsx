import { notFound } from "next/navigation";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ManualArticleView from "../_components/ManualArticle";
import ManualNav from "../_components/ManualNav";
import ManualPrintLink from "../_components/ManualPrintLink";
import { readManualArticle, readManualTree } from "../_lib/articles";
import { imageSizes } from "../_lib/imageSizes";

export default async function ManualArticlePage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  const article = readManualArticle(locale, slug);
  if (!article) notFound();
  const tree = readManualTree(locale);
  const markdown = article.body.replaceAll("{lang}", locale);

  return (
    <ProtectedRoute>
      <div className="relative px-4 sm:px-6 lg:px-8 pt-10 pb-20">
        <div className="absolute top-6 right-4 sm:right-6 lg:right-8">
          <ManualPrintLink />
        </div>
        <div className="flex flex-col lg:flex-row gap-8 lg:gap-12">
          <ManualNav tree={tree} activeSlug={slug} />
          <ManualArticleView markdown={markdown} sizes={imageSizes(markdown)} />
        </div>
      </div>
    </ProtectedRoute>
  );
}
