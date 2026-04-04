"use client";

import { useCaseContext } from "@/providers/case-provider";
import { DraftBanner } from "@/components/layout/draft-banner";
import { LoadingSkeleton } from "@/components/shared/loading-skeleton";
import { ErrorState } from "@/components/shared/error-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ConfidenceBadge } from "@/components/shared/confidence-badge";

export default function MotionsPage() {
  const { caseId, detail, isLoading, error } = useCaseContext();

  if (isLoading) return <LoadingSkeleton />;
  if (error) return <ErrorState message={error.message} />;

  const motionsData = detail?.draft_motions;

  return (
    <div className="space-y-4">
      <DraftBanner reviewStatus={detail?.review_status} />
      <h1 className="text-2xl font-bold text-slate-900">Draft Motions</h1>
      <p className="text-sm text-muted-foreground">Case: {caseId}</p>

      {!motionsData && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">
              No motions drafted yet. The Motion Drafter agent runs after case preparation is complete.
            </p>
          </CardContent>
        </Card>
      )}

      {motionsData && (
        <>
          <div className="flex items-center gap-2">
            <ConfidenceBadge level={motionsData.confidence} />
            <span className="text-xs text-muted-foreground">
              {motionsData.data.motions.length} motion{motionsData.data.motions.length !== 1 ? "s" : ""} drafted
            </span>
          </div>
          {motionsData.data.motions.map((motion) => (
            <Card key={motion.id}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  {motion.title}
                  <Badge variant="secondary">{motion.type}</Badge>
                  <Badge variant="outline">{motion.status}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {motion.filingDeadline && (
                  <p className="mb-2 text-sm text-pd-amber">
                    Filing deadline: {motion.filingDeadline}
                  </p>
                )}
                <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap rounded border bg-slate-50 p-4 text-xs">
                  {motion.draft}
                </pre>
                {motion.supportingAuthority.length > 0 && (
                  <div className="mt-2">
                    <p className="text-xs font-medium text-muted-foreground">Supporting Authority:</p>
                    <ul className="mt-1 list-inside list-disc text-xs text-muted-foreground">
                      {motion.supportingAuthority.map((auth, i) => (
                        <li key={i}>{auth}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </>
      )}
    </div>
  );
}
