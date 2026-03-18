import { formatStage, confidenceColor } from "@/lib/utils";

interface CaseCardProps {
  id: string;
  caseNumber?: string;
  stage: string;
  chargeCount: number;
  createdAt: string;
}

export function CaseCard({ id, caseNumber, stage, chargeCount, createdAt }: CaseCardProps) {
  return (
    <a
      href={`/cases/${id}`}
      style={{
        display: "block",
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        padding: "1rem",
        marginBottom: "0.75rem",
        textDecoration: "none",
        color: "inherit",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <strong>{caseNumber || `Case ${id.slice(0, 8)}`}</strong>
        <span style={{ fontSize: "0.85rem", color: "#6b7280" }}>
          {formatStage(stage)}
        </span>
      </div>
      <div style={{ fontSize: "0.85rem", color: "#6b7280", marginTop: "0.25rem" }}>
        {chargeCount} charge{chargeCount !== 1 ? "s" : ""} — Created {new Date(createdAt).toLocaleDateString()}
      </div>
    </a>
  );
}
