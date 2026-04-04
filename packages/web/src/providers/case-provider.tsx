"use client";

import { createContext, useContext, useMemo } from "react";
import type { CaseDetail, CaseStatusResponse } from "@/types/case";
import type { EthicalFlag } from "@/types/case";
import { useCase, useCaseStatus } from "@/hooks/use-case";
import { deriveAgentStatuses, type AgentKey, type AgentStatus } from "@/lib/events";

interface CaseContextValue {
  caseId: string;
  detail: CaseDetail | undefined;
  status: CaseStatusResponse | undefined;
  agentStatuses: Record<AgentKey, AgentStatus>;
  ethicalFlags: EthicalFlag[];
  isLoading: boolean;
  error: Error | undefined;
}

const CaseContext = createContext<CaseContextValue | null>(null);

interface CaseProviderProps {
  caseId: string;
  children: React.ReactNode;
}

export function CaseProvider({ caseId, children }: CaseProviderProps) {
  const { data: detail, error: detailError, isLoading: detailLoading } = useCase(caseId);
  const { data: status, error: statusError, isLoading: statusLoading } = useCaseStatus(caseId);

  const agentStatuses = useMemo(
    () => deriveAgentStatuses(detail as unknown as Record<string, unknown> | null),
    [detail]
  );

  const ethicalFlags = useMemo(
    () => detail?.ethical_flags ?? [],
    [detail]
  );

  const value = useMemo<CaseContextValue>(
    () => ({
      caseId,
      detail,
      status,
      agentStatuses,
      ethicalFlags,
      isLoading: detailLoading || statusLoading,
      error: detailError ?? statusError,
    }),
    [caseId, detail, status, agentStatuses, ethicalFlags, detailLoading, statusLoading, detailError, statusError]
  );

  return <CaseContext.Provider value={value}>{children}</CaseContext.Provider>;
}

export function useCaseContext(): CaseContextValue {
  const ctx = useContext(CaseContext);
  if (!ctx) {
    throw new Error("useCaseContext must be used within a CaseProvider");
  }
  return ctx;
}
