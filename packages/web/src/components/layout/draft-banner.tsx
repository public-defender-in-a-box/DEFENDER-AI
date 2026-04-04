import type { ReviewStatus } from "@/types/review";
import { hasUnreviewedSections } from "@/lib/mappers";

interface DraftBannerProps {
  /** Pass review status to conditionally hide when fully approved. */
  reviewStatus?: Record<string, ReviewStatus>;
}

export function DraftBanner({ reviewStatus }: DraftBannerProps) {
  // If review status is provided and all sections are approved, don't show
  if (reviewStatus && !hasUnreviewedSections(reviewStatus)) {
    return null;
  }

  return (
    <div className="draft-warning">
      DRAFT — ATTORNEY REVIEW REQUIRED
    </div>
  );
}
