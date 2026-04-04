import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format a pipeline stage for display */
export function formatStage(stage: string): string {
  return stage
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Format a confidence level with color hint */
export function confidenceColor(level: string): string {
  switch (level) {
    case "HIGH": return "#16a34a";
    case "MEDIUM": return "#d97706";
    case "LOW": return "#ef4444";
    default: return "#6b7280";
  }
}
