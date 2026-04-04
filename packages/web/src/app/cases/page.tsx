import { DraftBanner } from "@/components/layout/draft-banner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function CasesPage() {
  return (
    <div className="space-y-4">
      <DraftBanner />
      <h1 className="text-2xl font-bold text-slate-900">Cases</h1>
      <Card>
        <CardHeader>
          <CardTitle>All Cases</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Case list with pipeline status and quick actions. Coming in Phase 2.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
