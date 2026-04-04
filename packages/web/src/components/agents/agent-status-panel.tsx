"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AGENT_KEYS, AGENT_DISPLAY_NAMES, type AgentKey, type AgentStatus } from "@/lib/events";

interface AgentStatusPanelProps {
  statuses: Record<AgentKey, AgentStatus>;
}

function StatusIcon({ status }: { status: AgentStatus }) {
  switch (status) {
    case "COMPLETE":
      return <span className="text-pd-green" title="Complete">&#10003;</span>;
    case "RUNNING":
      return <span className="animate-spin text-pd-blue" title="Running">&#9696;</span>;
    case "FAILED":
      return <span className="text-pd-red" title="Failed">&#10007;</span>;
    case "QUEUED":
      return <span className="text-pd-amber" title="Queued">&#9679;</span>;
    case "NOT_STARTED":
      return <span className="text-slate-300" title="Not started">&mdash;</span>;
  }
}

function statusLabel(status: AgentStatus): string {
  switch (status) {
    case "COMPLETE": return "Complete";
    case "RUNNING": return "Running";
    case "FAILED": return "Failed";
    case "QUEUED": return "Queued";
    case "NOT_STARTED": return "Not started";
  }
}

function statusBgClass(status: AgentStatus): string {
  switch (status) {
    case "COMPLETE": return "bg-green-50 border-green-200";
    case "RUNNING": return "bg-blue-50 border-blue-200";
    case "FAILED": return "bg-red-50 border-red-200";
    case "QUEUED": return "bg-amber-50 border-amber-200";
    case "NOT_STARTED": return "bg-slate-50 border-slate-200";
  }
}

export function AgentStatusPanel({ statuses }: AgentStatusPanelProps) {
  const completedCount = AGENT_KEYS.filter((k) => statuses[k] === "COMPLETE").length;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Agent Pipeline</span>
          <span className="text-sm font-normal text-muted-foreground">
            {completedCount}/{AGENT_KEYS.length} complete
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-2">
          {AGENT_KEYS.map((key) => (
            <div
              key={key}
              className={`flex items-center gap-2 rounded border p-2 text-xs ${statusBgClass(statuses[key])}`}
            >
              <StatusIcon status={statuses[key]} />
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{AGENT_DISPLAY_NAMES[key]}</div>
                <div className="text-muted-foreground">{statusLabel(statuses[key])}</div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
