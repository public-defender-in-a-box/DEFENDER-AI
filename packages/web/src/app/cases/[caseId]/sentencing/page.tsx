"use client";

import { useCaseContext } from "@/providers/case-provider";
import { DraftBanner } from "@/components/layout/draft-banner";
import { LoadingSkeleton } from "@/components/shared/loading-skeleton";
import { ErrorState } from "@/components/shared/error-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfidenceBadge } from "@/components/shared/confidence-badge";

export default function SentencingPage() {
  const { caseId, detail, isLoading, error } = useCaseContext();

  if (isLoading) return <LoadingSkeleton />;
  if (error) return <ErrorState message={error.message} />;

  const sentData = detail?.sentencing_analysis;

  return (
    <div className="space-y-4">
      <DraftBanner reviewStatus={detail?.review_status} />
      <h1 className="text-2xl font-bold text-slate-900">Sentencing Analysis</h1>
      <p className="text-sm text-muted-foreground">Case: {caseId}</p>

      {!sentData && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">
              No sentencing analysis yet. This agent runs after case preparation is complete.
            </p>
          </CardContent>
        </Card>
      )}

      {sentData && (
        <>
          <ConfidenceBadge level={sentData.confidence} />

          <Card>
            <CardHeader>
              <CardTitle>Guideline Range</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Range</span>
                <p className="font-medium">
                  {sentData.data.guidelineRange.minimumMonths}–{sentData.data.guidelineRange.maximumMonths} months
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">Offense Level</span>
                <p className="font-medium">{sentData.data.guidelineRange.offenseLevel}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Criminal History</span>
                <p className="font-medium">{sentData.data.guidelineRange.criminalHistoryCategory}</p>
              </div>
            </CardContent>
          </Card>

          {sentData.data.departureArguments.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Departure Arguments</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {sentData.data.departureArguments.map((arg, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm">
                      <span className={`mt-0.5 text-xs font-semibold ${
                        arg.direction === "DOWNWARD" ? "text-pd-green" : "text-pd-red"
                      }`}>
                        {arg.direction}
                      </span>
                      <span className="flex-1">{arg.basis}</span>
                      <ConfidenceBadge level={arg.strength} />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {sentData.data.alternatives.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Alternatives to Incarceration</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {sentData.data.alternatives.map((alt, i) => (
                    <div key={i} className="text-sm">
                      <p className="font-medium">{alt.type}</p>
                      <p className="text-muted-foreground">{alt.description}</p>
                      <p className="text-xs text-muted-foreground">Eligibility: {alt.eligibility}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
