import { Badge } from "@/components/ui/badge";

interface FlagListProps {
  flags: string[];
}

function flagVariant(flag: string): "default" | "secondary" | "destructive" | "outline" {
  if (flag.startsWith("LOW_CONFIDENCE") || flag === "BIAS_CHECK") {
    return "destructive";
  }
  if (flag.startsWith("UNVERIFIED") || flag.startsWith("MISSING_")) {
    return "secondary";
  }
  if (flag === "DECISION_SUPPORT_ONLY" || flag === "TRIAL_MAY_BE_WARRANTED") {
    return "outline";
  }
  if (flag === "FIRST_OFFENDER_ELIGIBLE") {
    return "default";
  }
  return "secondary";
}

export function FlagList({ flags }: FlagListProps) {
  if (flags.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5">
      {flags.map((flag) => (
        <Badge key={flag} variant={flagVariant(flag)}>
          {flag.replace(/_/g, " ")}
        </Badge>
      ))}
    </div>
  );
}
