"use client";

import { useCaseContext } from "@/providers/case-provider";
import { DraftBanner } from "@/components/layout/draft-banner";
import { LoadingSkeleton } from "@/components/shared/loading-skeleton";
import { ErrorState } from "@/components/shared/error-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AGENT_KEYS, AGENT_DISPLAY_NAMES } from "@/lib/events";

export default function TimelinePage() {
  const { caseId, detail, status, agentStatuses, isLoading, error } = useCaseContext();

  if (isLoading) return <LoadingSkeleton />;
  if (error) return <ErrorState message={error.message} />;

  const completedAgents = AGENT_KEYS.filter((k) => agentStatuses[k] === "COMPLETE");

  return (
    <div className="space-y-4">
      <DraftBanner reviewStatus={detail?.review_status} />
      <h1 className="text-2xl font-bold text-slate-900">Case Timeline</h1>
      <p className="text-sm text-muted-foreground">Case: {caseId}</p>

      {status && (
        <Card>
          <CardHeader>
            <CardTitle>Pipeline Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>
              <span className="font-medium">Current Stage:</span>{" "}
              {status.current_stage}
            </p>
            {status.blocked && (
              <p className="text-pd-red">
                <span className="font-medium">Blocked:</span>{" "}
                {status.blocked_reason ?? "Unknown reason"}
              </p>
            )}
            {status.completed_stages.length > 0 && (
              <div>
                <span className="font-medium">Completed Stages:</span>
                <ul className="mt-1 list-inside list-disc text-muted-foreground">
                  {status.completed_stages.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Agent Completion Log</CardTitle>
        </CardHeader>
        <CardContent>
          {completedAgents.length === 0 ? (
            <p className="text-sm text-muted-foreground">No agents have completed yet.</p>
          ) : (
            <div className="space-y-2">
              {completedAgents.map((key) => (
                <div key={key} className="flex items-center gap-2 text-sm">
                  <span className="text-pd-green">&#10003;</span>
                  <span className="font-medium">{AGENT_DISPLAY_NAMES[key]}</span>
                  <span className="text-muted-foreground">— Complete</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
