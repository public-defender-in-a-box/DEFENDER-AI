"use client";

import type { ReviewSection } from "@/types/review";

interface CaseMemoReviewProps {
  sections: ReviewSection[];
}

export function CaseMemoReview({ sections }: CaseMemoReviewProps) {
  return (
    <div>
      {sections.map((section) => (
        <div
          key={section.sectionId}
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            padding: "1rem",
            marginBottom: "1rem",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
            <strong>{section.sectionTitle}</strong>
            <span style={{
              fontSize: "0.75rem",
              padding: "2px 8px",
              borderRadius: 4,
              background: section.status === "ATTORNEY_APPROVED" ? "#dcfce7" : "#fef3c7",
              color: section.status === "ATTORNEY_APPROVED" ? "#166534" : "#92400e",
            }}>
              {section.status.replace(/_/g, " ")}
            </span>
          </div>
          <div style={{ fontSize: "0.8rem", color: "#6b7280" }}>
            Review tier: {section.tier.replace(/_/g, " ")}
          </div>
        </div>
      ))}
    </div>
  );
}
