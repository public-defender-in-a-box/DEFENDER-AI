"use client";

import Link from "next/link";
import { useCases } from "@/hooks/use-case";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingSkeleton } from "@/components/shared/loading-skeleton";
import { ErrorState } from "@/components/shared/error-state";
import { Badge } from "@/components/ui/badge";
import { formatStage } from "@/lib/utils";

export default function CasesPage() {
  const { data: cases, error, isLoading } = useCases();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Cases</h1>
        <Link
          href="/upload"
          className="inline-flex items-center rounded-md bg-pd-blue px-4 py-2 text-sm font-medium text-white hover:bg-pd-blue-light"
        >
          Upload Document
        </Link>
      </div>

      {isLoading && <LoadingSkeleton />}
      {error && <ErrorState message={error.message} />}

      {cases && cases.length === 0 && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">
              No cases yet.{" "}
              <Link href="/upload" className="text-pd-blue underline">
                Upload a charging document
              </Link>{" "}
              to create one.
            </p>
          </CardContent>
        </Card>
      )}

      {cases && cases.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>All Cases</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="pb-2 font-medium">Case ID</th>
                  <th className="pb-2 font-medium">Stage</th>
                  <th className="pb-2 font-medium">Jurisdiction</th>
                  <th className="pb-2 font-medium">Created</th>
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => (
                  <tr key={c.id} className="border-b last:border-0">
                    <td className="py-3">
                      <Link
                        href={`/cases/${c.id}`}
                        className="font-medium text-pd-blue hover:underline"
                      >
                        {c.id}
                      </Link>
                    </td>
                    <td className="py-3">
                      <Badge variant="secondary">{formatStage(c.stage)}</Badge>
                    </td>
                    <td className="py-3">{c.jurisdiction}</td>
                    <td className="py-3 text-muted-foreground">
                      {new Date(c.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
