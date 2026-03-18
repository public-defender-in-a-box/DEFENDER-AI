interface Motion {
  id: string;
  type: string;
  title: string;
  status: string;
  filingDeadline: string | null;
}

interface MotionListProps {
  motions: Motion[];
}

export function MotionList({ motions }: MotionListProps) {
  return (
    <div>
      {motions.map((motion) => (
        <div
          key={motion.id}
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            padding: "1rem",
            marginBottom: "0.75rem",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <strong>{motion.title}</strong>
            <span style={{
              fontSize: "0.75rem",
              padding: "2px 8px",
              borderRadius: 4,
              background: "#fef3c7",
              color: "#92400e",
            }}>
              DRAFT
            </span>
          </div>
          <div style={{ fontSize: "0.8rem", color: "#6b7280", marginTop: "0.25rem" }}>
            Type: {motion.type}
            {motion.filingDeadline && ` — Deadline: ${new Date(motion.filingDeadline).toLocaleDateString()}`}
          </div>
        </div>
      ))}
    </div>
  );
}
