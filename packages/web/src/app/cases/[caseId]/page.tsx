"use client";

import { useCaseContext } from "@/providers/case-provider";
import { DraftBanner } from "@/components/layout/draft-banner";
import { AgentStatusPanel } from "@/components/agents/agent-status-panel";
import { EthicalFlagAlert } from "@/components/agents/ethical-flag-alert";
import { LoadingSkeleton } from "@/components/shared/loading-skeleton";
import { ErrorState } from "@/components/shared/error-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatStage } from "@/lib/utils";

export default function CaseDetailPage() {
  const { caseId, detail, agentStatuses, ethicalFlags, isLoading, error } = useCaseContext();

  if (isLoading) return <LoadingSkeleton />;
  if (error) return <ErrorState message={error.message} />;

  return (
    <div className="space-y-4">
      <DraftBanner reviewStatus={detail?.review_status} />
      <EthicalFlagAlert flags={ethicalFlags} caseId={caseId} />

      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold text-slate-900">Case: {caseId}</h1>
        {detail && (
          <Badge variant="secondary">{formatStage(detail.stage)}</Badge>
        )}
      </div>

      {detail && (
        <Card>
          <CardHeader>
            <CardTitle>Case Info</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Jurisdiction</span>
              <p className="font-medium">{detail.jurisdiction}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Stage</span>
              <p className="font-medium">{formatStage(detail.stage)}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Created</span>
              <p className="font-medium">
                {new Date(detail.created_at).toLocaleDateString()}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      <AgentStatusPanel statuses={agentStatuses} />
    </div>
  );
}
