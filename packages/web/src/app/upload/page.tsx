"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { DraftBanner } from "@/components/layout/draft-banner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/shared/error-state";
import { api, ApiError } from "@/lib/api-client";

const DOCUMENT_TYPES = [
  { value: "COMPLAINT", label: "Criminal Complaint" },
  { value: "INDICTMENT", label: "Indictment" },
  { value: "ARREST_REPORT", label: "Arrest Report" },
  { value: "OTHER", label: "Other" },
];

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [docType, setDocType] = useState("COMPLAINT");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      const result = await api.upload.document(file, docType, "GA");
      router.push(`/cases/${result.case_id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Upload failed. Please try again.");
      }
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-4">
      <DraftBanner />
      <h1 className="text-2xl font-bold text-slate-900">
        Upload Charging Document
      </h1>

      {error && <ErrorState message={error} />}

      <Card className="max-w-lg">
        <CardHeader>
          <CardTitle>New Case</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="docType">Document Type</Label>
              <select
                id="docType"
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {DOCUMENT_TYPES.map((dt) => (
                  <option key={dt.value} value={dt.value}>
                    {dt.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="file">File (PDF, PNG, JPG)</Label>
              <Input
                id="file"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.txt"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>

            <Button type="submit" disabled={!file || uploading}>
              {uploading ? "Uploading..." : "Upload & Process"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
