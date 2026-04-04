"use client";

import useSWR from "swr";
import type { CaseSummary, CaseDetail, CaseState, CaseStatusResponse } from "@/types/case";
import type { MotionDrafterOutput, PleaTrialOutput, SentencingOutput, BradyAnalysisOutput } from "@/types/agents";
import { api } from "@/lib/api-client";
import { mapCaseDetailToCaseState } from "@/lib/mappers";

/** Polling interval for active cases (3 seconds). */
const ACTIVE_REFRESH = 3000;

/** Polling interval for stable/inactive data (30 seconds). */
const STABLE_REFRESH = 30000;

// --- SWR fetcher wrappers ---
// SWR needs a string key; these closures use the api client internally.

export function useCases() {
  return useSWR<CaseSummary[]>("cases:list", () => api.cases.list(), {
    refreshInterval: STABLE_REFRESH,
  });
}

export function useCase(caseId: string | null) {
  return useSWR<CaseDetail>(
    caseId ? `cases:${caseId}` : null,
    () => api.cases.get(caseId!),
    { refreshInterval: ACTIVE_REFRESH }
  );
}

export function useCaseState(caseId: string | null) {
  const { data: detail, error, isLoading, mutate } = useCase(caseId);
  return {
    data: detail ? mapCaseDetailToCaseState(detail) : undefined,
    error,
    isLoading,
    mutate,
  };
}

export function useCaseStatus(caseId: string | null) {
  return useSWR<CaseStatusResponse>(
    caseId ? `cases:${caseId}:status` : null,
    () => api.cases.status(caseId!),
    { refreshInterval: ACTIVE_REFRESH }
  );
}

// --- Agent output hooks (derived from cached CaseDetail) ---

export function useMotions(caseId: string | null) {
  const { data: detail, error, isLoading } = useCase(caseId);
  const motions: MotionDrafterOutput | undefined = detail?.draft_motions?.data;
  return { data: motions, error, isLoading };
}

export function usePleaTrial(caseId: string | null) {
  const { data: detail, error, isLoading } = useCase(caseId);
  const assessment: PleaTrialOutput | undefined = detail?.plea_trial_assessment?.data;
  return { data: assessment, error, isLoading };
}

export function useSentencing(caseId: string | null) {
  const { data: detail, error, isLoading } = useCase(caseId);
  const analysis: SentencingOutput | undefined = detail?.sentencing_analysis?.data;
  return { data: analysis, error, isLoading };
}

export function useBrady(caseId: string | null) {
  const { data: detail, error, isLoading } = useCase(caseId);
  const analysis: BradyAnalysisOutput | undefined = detail?.brady_analysis?.data;
  return { data: analysis, error, isLoading };
}
