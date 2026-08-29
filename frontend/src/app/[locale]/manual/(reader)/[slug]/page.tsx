import { notFound } from "next/navigation";
import ManualArticleView from "../../_components/ManualArticle";
import { readManualArticle } from "../../_lib/articles";
import { imageSizes } from "../../_lib/imageSizes";

export default async function ManualArticlePage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  const article = readManualArticle(locale, slug);
  if (!article) notFound();
  const markdown = article.body.replaceAll("{lang}", locale);

  return <ManualArticleView markdown={markdown} sizes={imageSizes(markdown)} />;
}
