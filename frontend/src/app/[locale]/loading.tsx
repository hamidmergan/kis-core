import Spinner from "@/components/ui/Spinner";

/** Fills the gap between the click and the arrival of the next page. */
export default function Loading() {
  return (
    <div className="flex items-center justify-center min-h-[50vh]">
      <Spinner size="lg" />
    </div>
  );
}
