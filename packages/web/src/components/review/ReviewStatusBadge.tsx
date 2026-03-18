import type { ReviewStatus } from "@/types/review";

interface ReviewStatusBadgeProps {
  status: ReviewStatus;
}

const statusConfig: Record<ReviewStatus, { bg: string; color: string; label: string }> = {
  PENDING_REVIEW: { bg: "#fee2e2", color: "#991b1b", label: "Pending Review" },
  IN_REVIEW: { bg: "#fef3c7", color: "#92400e", label: "In Review" },
  ATTORNEY_APPROVED: { bg: "#dcfce7", color: "#166534", label: "Approved" },
};

export function ReviewStatusBadge({ status }: ReviewStatusBadgeProps) {
  const config = statusConfig[status];
  return (
    <span style={{
      fontSize: "0.75rem",
      padding: "2px 8px",
      borderRadius: 4,
      background: config.bg,
      color: config.color,
      fontWeight: 600,
    }}>
      {config.label}
    </span>
  );
}
