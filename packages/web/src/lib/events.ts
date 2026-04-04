"use client";

/**
 * Agent status types for the real-time event system.
 *
 * The backend does not yet expose an SSE endpoint. This module provides a
 * polling-based fallback that derives agent statuses from the CaseDetail
 * response. When the backend adds `/api/v1/cases/:id/events` (SSE), swap
 * the implementation here without changing consumers.
 */

export type AgentStatus = "NOT_STARTED" | "QUEUED" | "RUNNING" | "COMPLETE" | "FAILED";

export const AGENT_KEYS = [
  "charge_processing",
  "pre_interview_research",
  "intake_summary",
  "case_prep_memo",
  "statute_analysis",
  "case_law_research",
  "citation_verification",
  "fact_gathering",
  "rights_violation_analysis",
  "collateral_consequences",
  "personal_circumstances",
  "draft_motions",
  "brady_analysis",
  "plea_trial_assessment",
  "sentencing_analysis",
] as const;

export type AgentKey = (typeof AGENT_KEYS)[number];

export const AGENT_DISPLAY_NAMES: Record<AgentKey, string> = {
  charge_processing: "Charge Processing",
  pre_interview_research: "Pre-Interview Research",
  intake_summary: "Intake Conductor",
  case_prep_memo: "Case Prep",
  statute_analysis: "Statute Agent",
  case_law_research: "Case Law Agent",
  citation_verification: "Citation Verifier",
  fact_gathering: "Fact Gatherer",
  rights_violation_analysis: "Rights Scanner",
  collateral_consequences: "Collateral Agent",
  personal_circumstances: "Personal Circumstances",
  draft_motions: "Motion Drafter",
  brady_analysis: "Brady Agent",
  plea_trial_assessment: "Plea/Trial Analyst",
  sentencing_analysis: "Sentencing Agent",
};

/**
 * Derive agent statuses from a CaseDetail response.
 * This is the polling fallback; replace with SSE parsing when available.
 */
export function deriveAgentStatuses(
  caseDetail: Record<string, unknown> | null
): Record<AgentKey, AgentStatus> {
  const statuses = {} as Record<AgentKey, AgentStatus>;

  for (const key of AGENT_KEYS) {
    const value = caseDetail?.[key];
    if (value !== null && value !== undefined) {
      statuses[key] = "COMPLETE";
    } else {
      statuses[key] = "NOT_STARTED";
    }
  }

  return statuses;
}
