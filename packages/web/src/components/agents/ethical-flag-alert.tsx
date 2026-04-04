import Link from "next/link";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type { EthicalFlag } from "@/types/case";

interface EthicalFlagAlertProps {
  flags: EthicalFlag[];
  caseId: string;
}

export function EthicalFlagAlert({ flags, caseId }: EthicalFlagAlertProps) {
  const blockedFlags = flags.filter((f) => f.blocked);
  if (blockedFlags.length === 0) return null;

  return (
    <Alert variant="destructive">
      <AlertTitle>
        Ethical Flag{blockedFlags.length > 1 ? "s" : ""} — Agent Output Blocked
      </AlertTitle>
      <AlertDescription>
        <ul className="mt-2 space-y-1 text-sm">
          {blockedFlags.map((flag) => (
            <li key={flag.id}>
              <span className="font-semibold">{flag.category}</span>: {flag.description}
              <span className="ml-1 text-xs text-muted-foreground">
                (from {flag.agentSource})
              </span>
            </li>
          ))}
        </ul>
        <Link
          href={`/cases/${caseId}/review`}
          className="mt-2 inline-block text-sm font-medium underline"
        >
          Go to Review
        </Link>
      </AlertDescription>
    </Alert>
  );
}
