import { DraftBanner } from "@/components/layout/draft-banner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function MotionsPage({
  params,
}: {
  params: { caseId: string };
}) {
  return (
    <div className="space-y-4">
      <DraftBanner />
      <h1 className="text-2xl font-bold text-slate-900">Draft Motions</h1>
      <p className="text-sm text-muted-foreground">Case: {params.caseId}</p>
      <Card>
        <CardHeader>
          <CardTitle>Motions</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Draft motions with attorney editing interface. Coming in Phase 2.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
