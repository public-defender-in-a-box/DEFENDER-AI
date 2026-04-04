import type { CaseDetail, CaseState, ConfidenceLevel, ReviewStatus } from "@/types/case";

/**
 * Maps a snake_case CaseDetail API response to a camelCase CaseState object.
 * The backend returns snake_case keys; the frontend CaseState uses camelCase.
 */
export function mapCaseDetailToCaseState(detail: CaseDetail): CaseState {
  return {
    id: detail.id,
    createdAt: detail.created_at,
    updatedAt: detail.created_at, // Backend doesn't expose updated_at separately
    jurisdiction: detail.jurisdiction,
    stage: detail.stage as CaseState["stage"],
    stageHistory: [],
    attorneyId: "",
    attorneyConfig: {
      jurisdiction: detail.jurisdiction,
      preferences: {},
    },

    // Tier 1 Outputs
    chargeProcessing: detail.charge_processing,
    preInterviewResearch: detail.pre_interview_research,
    intakeSummary: detail.intake_summary,
    casePrepMemo: detail.case_prep_memo,

    // Tier 2 Research Outputs
    statuteAnalysis: detail.statute_analysis,
    caseLawResearch: detail.case_law_research,
    citationVerification: detail.citation_verification,

    // Tier 2 Intake Outputs
    factGathering: detail.fact_gathering,
    rightsViolationAnalysis: detail.rights_violation_analysis,
    collateralConsequences: detail.collateral_consequences,
    personalCircumstances: detail.personal_circumstances,

    // Tier 2 Attorney Prep Outputs
    draftMotions: detail.draft_motions,
    bradyAnalysis: detail.brady_analysis,
    pleaTrialAssessment: detail.plea_trial_assessment,
    sentencingAnalysis: detail.sentencing_analysis,

    // Cross-cutting
    ethicalFlags: detail.ethical_flags ?? [],
    auditLog: [],

    // Attorney Review
    reviewStatus: detail.review_status ?? {},

    // Documents
    documents: [],
  };
}

/**
 * Checks if any section in the review status map is still pending review.
 */
export function hasUnreviewedSections(
  reviewStatus: Record<string, ReviewStatus>
): boolean {
  const statuses = Object.values(reviewStatus);
  if (statuses.length === 0) return true; // No review data yet = unreviewed
  return statuses.some((s) => s !== "ATTORNEY_APPROVED");
}

/**
 * Maps a confidence level string to a consistent hex color.
 * Uses the same values as the Tailwind config (pd-green, pd-amber, pd-red).
 */
export function confidenceLevelToColor(level: ConfidenceLevel): string {
  switch (level) {
    case "HIGH":
      return "#16a34a";
    case "MEDIUM":
      return "#d97706";
    case "LOW":
      return "#dc2626";
    case "UNRATED":
      return "#6b7280";
  }
}
