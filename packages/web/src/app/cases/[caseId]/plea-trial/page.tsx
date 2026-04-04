"use client";

import { useCaseContext } from "@/providers/case-provider";
import { DraftBanner } from "@/components/layout/draft-banner";
import { LoadingSkeleton } from "@/components/shared/loading-skeleton";
import { ErrorState } from "@/components/shared/error-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfidenceBadge } from "@/components/shared/confidence-badge";

export default function PleaTrialPage() {
  const { caseId, detail, isLoading, error } = useCaseContext();

  if (isLoading) return <LoadingSkeleton />;
  if (error) return <ErrorState message={error.message} />;

  const ptData = detail?.plea_trial_assessment;

  return (
    <div className="space-y-4">
      <DraftBanner reviewStatus={detail?.review_status} />
      <h1 className="text-2xl font-bold text-slate-900">Plea / Trial Assessment</h1>
      <p className="text-sm text-muted-foreground">Case: {caseId}</p>

      <div className="draft-warning">DECISION SUPPORT ONLY</div>

      {!ptData && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">
              No plea/trial assessment yet. This agent runs after case preparation is complete.
            </p>
          </CardContent>
        </Card>
      )}

      {ptData && (
        <>
          <ConfidenceBadge level={ptData.confidence} />

          <div className="grid grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Plea Scenario</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p><span className="font-medium">Charges:</span> {ptData.data.pleaScenario.charges.join(", ")}</p>
                <p><span className="font-medium">Sentencing Range:</span> {ptData.data.pleaScenario.sentencingRange}</p>
                {ptData.data.pleaScenario.collateralConsequences.length > 0 && (
                  <div>
                    <span className="font-medium">Collateral:</span>
                    <ul className="mt-1 list-inside list-disc text-muted-foreground">
                      {ptData.data.pleaScenario.collateralConsequences.map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Trial Scenario</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p><span className="font-medium">Charges:</span> {ptData.data.trialScenario.charges.join(", ")}</p>
                <p><span className="font-medium">Acquittal Probability:</span> {(ptData.data.trialScenario.acquittalProbability * 100).toFixed(0)}%</p>
                <p><span className="font-medium">If Convicted:</span> {ptData.data.trialScenario.sentencingIfConvicted}</p>
              </CardContent>
            </Card>
          </div>

          {ptData.data.riskFactors.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Risk Factors</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-inside list-disc space-y-1 text-sm">
                  {ptData.data.riskFactors.map((rf, i) => (
                    <li key={i}>{rf}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm">{ptData.data.recommendation}</p>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
