import { DraftBanner } from "@/components/layout/draft-banner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function PleaTrialPage({
  params,
}: {
  params: { caseId: string };
}) {
  return (
    <div className="space-y-4">
      <DraftBanner />
      <h1 className="text-2xl font-bold text-slate-900">Plea / Trial Assessment</h1>
      <p className="text-sm text-muted-foreground">Case: {params.caseId}</p>
      <Card>
        <CardHeader>
          <CardTitle>DECISION SUPPORT ONLY</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Plea vs. trial comparison matrix and risk analysis. Coming in Phase 2.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
