import { formatStage } from "@/lib/utils";

interface StageEntry {
  stage: string;
  enteredAt: string;
  exitedAt?: string;
}

interface CaseTimelineProps {
  stages: StageEntry[];
  currentStage: string;
}

export function CaseTimeline({ stages, currentStage }: CaseTimelineProps) {
  return (
    <div>
      <h3>Pipeline Timeline</h3>
      <ol style={{ listStyle: "none", padding: 0 }}>
        {stages.map((s, i) => (
          <li
            key={i}
            style={{
              padding: "0.5rem",
              borderLeft: `3px solid ${s.stage === currentStage ? "#3b82f6" : "#d1d5db"}`,
              marginBottom: "0.25rem",
              paddingLeft: "1rem",
            }}
          >
            <strong>{formatStage(s.stage)}</strong>
            <div style={{ fontSize: "0.8rem", color: "#6b7280" }}>
              {new Date(s.enteredAt).toLocaleString()}
              {s.exitedAt && ` — ${new Date(s.exitedAt).toLocaleString()}`}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
