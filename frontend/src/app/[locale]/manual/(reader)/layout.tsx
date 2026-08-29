import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ManualNav from "../_components/ManualNav";
import ManualPrintLink from "../_components/ManualPrintLink";
import { readManualTree } from "../_lib/articles";

/** Rahmen um alle Artikel, damit die Liste beim Wechsel stehen bleibt statt neu aufzubauen. */
export default async function ManualReaderLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const tree = readManualTree(locale);

  return (
    <ProtectedRoute>
      <div className="relative px-4 sm:px-6 lg:px-8 pt-10 pb-20">
        <div className="flex justify-end mb-6 sm:absolute sm:top-6 sm:right-6 sm:mb-0 lg:right-8">
          <ManualPrintLink />
        </div>
        <div className="flex flex-col lg:flex-row gap-8 lg:gap-12">
          <ManualNav tree={tree} />
          {children}
        </div>
      </div>
    </ProtectedRoute>
  );
}
