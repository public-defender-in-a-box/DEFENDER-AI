import { DraftBanner } from "@/components/layout/draft-banner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function CaseDetailPage({
  params,
}: {
  params: { caseId: string };
}) {
  return (
    <div className="space-y-4">
      <DraftBanner />
      <h1 className="text-2xl font-bold text-slate-900">
        Case: {params.caseId}
      </h1>
      <Card>
        <CardHeader>
          <CardTitle>Case Overview</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Parsed charges, pipeline status, and case summary. Coming in Phase 2.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
