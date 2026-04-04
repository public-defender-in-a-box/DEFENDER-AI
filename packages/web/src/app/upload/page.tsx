import { DraftBanner } from "@/components/layout/draft-banner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function UploadPage() {
  return (
    <div className="space-y-4">
      <DraftBanner />
      <h1 className="text-2xl font-bold text-slate-900">Upload Charging Document</h1>
      <Card>
        <CardHeader>
          <CardTitle>New Case</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Upload a criminal complaint, indictment, or arrest report to begin case processing.
            Coming in Phase 2.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
