import type { ConfidenceLevel } from "@/types/case";

interface ConfidenceBadgeProps {
  level: ConfidenceLevel;
  score?: number;
}

const badgeClass: Record<string, string> = {
  HIGH: "badge-high",
  MEDIUM: "badge-medium",
  LOW: "badge-low",
  UNRATED: "inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600",
};

export function ConfidenceBadge({ level, score }: ConfidenceBadgeProps) {
  return (
    <span className={badgeClass[level] ?? badgeClass.UNRATED}>
      {level}
      {score !== undefined && (
        <span className="ml-1 opacity-75">({(score * 100).toFixed(0)}%)</span>
      )}
    </span>
  );
}
