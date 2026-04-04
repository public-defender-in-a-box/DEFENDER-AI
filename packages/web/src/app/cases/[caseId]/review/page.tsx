"use client";

import { useCaseContext } from "@/providers/case-provider";
import { DraftBanner } from "@/components/layout/draft-banner";
import { LoadingSkeleton } from "@/components/shared/loading-skeleton";
import { ErrorState } from "@/components/shared/error-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EthicalFlagAlert } from "@/components/agents/ethical-flag-alert";

export default function ReviewPage() {
  const { caseId, detail, ethicalFlags, isLoading, error } = useCaseContext();

  if (isLoading) return <LoadingSkeleton />;
  if (error) return <ErrorState message={error.message} />;

  const reviewStatus = detail?.review_status ?? {};
  const sections = Object.entries(reviewStatus);

  return (
    <div className="space-y-4">
      <DraftBanner reviewStatus={reviewStatus} />
      <h1 className="text-2xl font-bold text-slate-900">Attorney Review</h1>
      <p className="text-sm text-muted-foreground">Case: {caseId}</p>

      <EthicalFlagAlert flags={ethicalFlags} caseId={caseId} />

      {sections.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">
              No sections ready for review yet. Sections become available as agents complete their analysis.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {sections.map(([sectionId, status]) => (
            <Card key={sectionId}>
              <CardHeader className="py-3">
                <CardTitle className="flex items-center justify-between text-base">
                  <span>{sectionId.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}</span>
                  <Badge
                    variant={status === "ATTORNEY_APPROVED" ? "default" : "secondary"}
                  >
                    {status}
                  </Badge>
                </CardTitle>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
