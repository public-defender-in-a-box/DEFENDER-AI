/** Pipeline stage tracking */
export type PipelineStage =
  | "CREATED"
  | "CHARGES_PROCESSING"
  | "CHARGES_PROCESSED"
  | "PRE_INTERVIEW_RESEARCH"
  | "PRE_INTERVIEW_COMPLETE"
  | "INTAKE_IN_PROGRESS"
  | "INTAKE_COMPLETE"
  | "CASE_PREP_IN_PROGRESS"
  | "CASE_PREP_COMPLETE"
  | "ATTORNEY_REVIEW"
  | "ATTORNEY_APPROVED";

export type ConfidenceLevel = "HIGH" | "MEDIUM" | "LOW" | "UNRATED";
export type VerificationStatus =
  | "VERIFIED"
  | "UNVERIFIED"
  | "CONFIRMED"
  | "UNCONFIRMED"
  | "OVERRULED"
  | "SUPERSEDED";
export type ReviewStatus = "PENDING_REVIEW" | "IN_REVIEW" | "ATTORNEY_APPROVED";
export type EthicalFlagPriority = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export interface ConfidenceRated<T> {
  data: T;
  confidence: ConfidenceLevel;
  source: string;
  timestamp: string;
}

export interface EthicalFlag {
  id: string;
  agentSource: string;
  category:
    | "PRIVILEGE"
    | "UPL"
    | "BIAS"
    | "COMPETENCE"
    | "CANDOR"
    | "IAC";
  priority: EthicalFlagPriority;
  description: string;
  blocked: boolean;
  resolvedBy?: string;
  resolvedAt?: string;
  resolution?: string;
}

export interface AuditEntry {
  id: string;
  timestamp: string;
  agentId: string;
  action: string;
  details: Record<string, unknown>;
  ethicalCheck: boolean;
}

/** The canonical case state object — single source of truth */
export interface CaseState {
  // Identity
  id: string;
  createdAt: string;
  updatedAt: string;
  jurisdiction: string;
  caseNumber?: string;

  // Pipeline
  stage: PipelineStage;
  stageHistory: Array<{
    stage: PipelineStage;
    enteredAt: string;
    exitedAt?: string;
  }>;

  // Attorney
  attorneyId: string;
  attorneyConfig: {
    jurisdiction: string;
    preferences: Record<string, unknown>;
  };

  // Tier 1 Outputs
  chargeProcessing: ConfidenceRated<ChargeProcessingOutput> | null;
  preInterviewResearch: ConfidenceRated<PreInterviewResearchOutput> | null;
  intakeSummary: ConfidenceRated<IntakeSummaryOutput> | null;
  casePrepMemo: ConfidenceRated<CasePrepOutput> | null;

  // Tier 2 Research Outputs
  statuteAnalysis: ConfidenceRated<StatuteAnalysisOutput> | null;
  caseLawResearch: ConfidenceRated<CaseLawOutput> | null;
  citationVerification: ConfidenceRated<CitationVerificationOutput> | null;

  // Tier 2 Intake Outputs
  factGathering: ConfidenceRated<FactGatheringOutput> | null;
  rightsViolationAnalysis: ConfidenceRated<RightsViolationOutput> | null;
  collateralConsequences: ConfidenceRated<CollateralConsequencesOutput> | null;
  personalCircumstances: ConfidenceRated<PersonalCircumstancesOutput> | null;

  // Tier 2 Attorney Prep Outputs
  draftMotions: ConfidenceRated<MotionDrafterOutput> | null;
  bradyAnalysis: ConfidenceRated<BradyAnalysisOutput> | null;
  pleaTrialAssessment: ConfidenceRated<PleaTrialOutput> | null;
  sentencingAnalysis: ConfidenceRated<SentencingOutput> | null;

  // Cross-cutting
  ethicalFlags: EthicalFlag[];
  auditLog: AuditEntry[];

  // Attorney Review
  reviewStatus: Record<string, ReviewStatus>;

  // Raw documents
  documents: Array<{
    id: string;
    type: "COMPLAINT" | "INDICTMENT" | "ARREST_REPORT" | "DISCOVERY" | "OTHER";
    fileName: string;
    storageUrl: string;
    uploadedAt: string;
  }>;
}

// --- API-facing summary types (for list/detail endpoints) ---

export interface CaseSummary {
  id: string;
  stage: string;
  jurisdiction: string;
  created_at: string;
}

export interface CaseDetail {
  id: string;
  stage: string;
  jurisdiction: string;
  created_at: string;
  charge_processing: ConfidenceRated<ChargeProcessingOutput> | null;
  pre_interview_research: ConfidenceRated<PreInterviewResearchOutput> | null;
  intake_summary: ConfidenceRated<IntakeSummaryOutput> | null;
  case_prep_memo: ConfidenceRated<CasePrepOutput> | null;
  statute_analysis: ConfidenceRated<StatuteAnalysisOutput> | null;
  case_law_research: ConfidenceRated<CaseLawOutput> | null;
  citation_verification: ConfidenceRated<CitationVerificationOutput> | null;
  fact_gathering: ConfidenceRated<FactGatheringOutput> | null;
  rights_violation_analysis: ConfidenceRated<RightsViolationOutput> | null;
  collateral_consequences: ConfidenceRated<CollateralConsequencesOutput> | null;
  personal_circumstances: ConfidenceRated<PersonalCircumstancesOutput> | null;
  draft_motions: ConfidenceRated<MotionDrafterOutput> | null;
  brady_analysis: ConfidenceRated<BradyAnalysisOutput> | null;
  plea_trial_assessment: ConfidenceRated<PleaTrialOutput> | null;
  sentencing_analysis: ConfidenceRated<SentencingOutput> | null;
  ethical_flags: EthicalFlag[];
  review_status: Record<string, ReviewStatus>;
}

export interface CaseStatusResponse {
  current_stage: string;
  completed_stages: string[];
  blocked: boolean;
  blocked_reason?: string;
}

export interface UploadResponse {
  case_id: string;
  file_name: string;
  document_type: string;
  jurisdiction: string;
  text_length: number;
  status: string;
  summary_url: string;
  status_url: string;
  message: string;
}

// Forward declarations — full definitions in agents.ts
export type ChargeProcessingOutput = import("./agents").ChargeProcessingOutput;
export type PreInterviewResearchOutput = import("./agents").PreInterviewResearchOutput;
export type IntakeSummaryOutput = import("./agents").IntakeSummaryOutput;
export type CasePrepOutput = import("./agents").CasePrepOutput;
export type StatuteAnalysisOutput = import("./agents").StatuteAnalysisOutput;
export type CaseLawOutput = import("./agents").CaseLawOutput;
export type CitationVerificationOutput = import("./agents").CitationVerificationOutput;
export type FactGatheringOutput = import("./agents").FactGatheringOutput;
export type RightsViolationOutput = import("./agents").RightsViolationOutput;
export type CollateralConsequencesOutput = import("./agents").CollateralConsequencesOutput;
export type PersonalCircumstancesOutput = import("./agents").PersonalCircumstancesOutput;
export type MotionDrafterOutput = import("./agents").MotionDrafterOutput;
export type BradyAnalysisOutput = import("./agents").BradyAnalysisOutput;
export type PleaTrialOutput = import("./agents").PleaTrialOutput;
export type SentencingOutput = import("./agents").SentencingOutput;
