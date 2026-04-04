import type { VerificationStatus } from "@/types/case";

interface VerificationTagProps {
  status: VerificationStatus;
}

const statusStyles: Record<VerificationStatus, string> = {
  VERIFIED: "text-green-700 font-medium",
  CONFIRMED: "text-green-700 font-medium",
  UNVERIFIED: "text-amber-600 font-medium italic",
  UNCONFIRMED: "text-amber-600 font-medium italic",
  OVERRULED: "text-red-600 font-medium line-through",
  SUPERSEDED: "text-red-600 font-medium",
};

export function VerificationTag({ status }: VerificationTagProps) {
  return (
    <span className={`text-xs ${statusStyles[status]}`}>
      [{status}]
    </span>
  );
}
