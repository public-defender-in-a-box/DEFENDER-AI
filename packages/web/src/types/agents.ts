import type { ConfidenceLevel, VerificationStatus } from "./case";

// ============================================================
// CHARGE PROCESSING AGENT
// ============================================================

export interface ChargeProcessingInput {
  documentText: string;
  documentType: "COMPLAINT" | "INDICTMENT" | "INFORMATION" | "ARREST_REPORT";
  jurisdiction: string;
}

export interface ParsedCharge {
  chargeId: string;
  statuteSection: string;
  offenseTitle: string;
  degree: string;
  elements: string[];
  penaltyRange: {
    minimumMonths: number | null;
    maximumMonths: number | null;
    fineMin: number | null;
    fineMax: number | null;
    mandatoryMinimum: boolean;
    probationEligible: boolean;
  };
  enhancements: Enhancement[];
  proceduralRequirements: string[];
}

export interface Enhancement {
  type: "WEAPON" | "PRIOR_RECORD" | "SCHOOL_ZONE" | "GANG" | "AMOUNT" | "OTHER";
  description: string;
  statuteSection: string;
  additionalPenalty: string;
}

export interface FactualAllegation {
  id: string;
  allegation: string;
  relatedChargeIds: string[];
  relatedElements: string[];
  dateOfAllegation?: string;
  location?: string;
}

export interface PersonOfInterest {
  name: string;
  role: "OFFICER" | "WITNESS" | "VICTIM" | "CO_DEFENDANT" | "OTHER";
  badgeNumber?: string;
  agency?: string;
  details: string;
}

export interface ChargeProcessingOutput {
  charges: ParsedCharge[];
  factualAllegations: FactualAllegation[];
  enhancements: Enhancement[];
  personsOfInterest: PersonOfInterest[];
  proceduralFlags: string[];
  rawDocumentSummary: string;
}

// ============================================================
// PRE-INTERVIEW RESEARCH CONDUCTOR
// ============================================================

export interface PreInterviewResearchOutput {
  chargesSummary: string;
  targetedQuestions: Array<{
    question: string;
    relevantChargeId: string;
    relevantElement: string;
    priority: "MUST_ASK" | "SHOULD_ASK" | "IF_TIME";
  }>;
  preliminaryRightsFlags: string[];
  knownFactsFromDocuments: string[];
  legalBrief: string;
}

// ============================================================
// INTAKE CONDUCTOR
// ============================================================

export interface IntakeConductorInput {
  preInterviewBrief: {
    chargesSummary: string;
    targetedQuestions: Array<{
      question: string;
      relevantChargeId: string;
      relevantElement: string;
      priority: "MUST_ASK" | "SHOULD_ASK" | "IF_TIME";
    }>;
    preliminaryRightsFlags: string[];
    knownFactsFromDocuments: string[];
  };
  clientSession: {
    sessionId: string;
    language: string;
    accessibilityNeeds: string[];
    previousSessionIds: string[];
  };
}

export interface IntakeMessage {
  id: string;
  timestamp: string;
  sender: "SYSTEM" | "CLIENT";
  content: string;
  generatedBy?:
    | "INTAKE_CONDUCTOR"
    | "FACT_GATHERER"
    | "RIGHTS_SCANNER"
    | "COLLATERAL_AGENT"
    | "PERSONAL_CIRCUMSTANCES";
  targetElement?: string;
}

export interface IntakeFactItem {
  id: string;
  category:
    | "ARREST_TIMELINE"
    | "WITNESS"
    | "EVIDENCE"
    | "OFFICER_CONDUCT"
    | "RIGHTS"
    | "PERSONAL"
    | "OTHER";
  statement: string;
  confidence: ConfidenceLevel;
  sourceMessageIds: string[];
  contradicts?: string[];
}

export interface InconsistencyFlag {
  id: string;
  clientStatement: string;
  documentStatement: string;
  severity: "CRITICAL" | "NOTABLE" | "MINOR";
  possibleExplanations: string[];
}

export interface IntakeSummaryOutput {
  sessionId: string;
  completedAt: string;
  completionPercentage: number;
  facts: IntakeFactItem[];
  inconsistencies: InconsistencyFlag[];
  personalCircumstances: {
    citizenship: string;
    employmentStatus: string;
    housingStatus: string;
    dependents: number;
    mentalHealthHistory: string | null;
    substanceAbuseHistory: string | null;
    militaryService: boolean;
    educationStatus: string;
    priorRecordSelfReport: string;
  };
  unansweredQuestions: Array<{
    question: string;
    reason: "CLIENT_DECLINED" | "SESSION_ENDED" | "NOT_APPLICABLE";
  }>;
  transcript: IntakeMessage[];
}

// ============================================================
// CASE PREP CONDUCTOR
// ============================================================

export interface CasePrepOutput {
  caseTheory: string;
  preparationMemo: string;
  decisionPoints: Array<{
    id: string;
    description: string;
    options: string[];
    recommendation: string;
    humanRequired: boolean;
  }>;
  attorneyTaskList: Array<{
    id: string;
    task: string;
    priority: "URGENT" | "HIGH" | "MEDIUM" | "LOW";
    deadline?: string;
    category: string;
  }>;
}

// ============================================================
// STATUTE AGENT
// ============================================================

export interface StatuteAnalysisOutput {
  statutes: Array<{
    statuteSection: string;
    fullText: string;
    elementsBreakdown: string[];
    relatedStatutes: string[];
    sentencingGuidelines: string;
    mandatoryMinimums: string | null;
    diversionEligibility: string;
    lastAmended: string | null;
    verificationStatus: VerificationStatus;
  }>;
  proceduralStatutes: string[];
  enhancementStatutes: string[];
}

// ============================================================
// CASE LAW AGENT
// ============================================================

export interface CaseLawOutput {
  authorities: Array<{
    caseName: string;
    citation: string;
    court: string;
    year: number;
    holding: string;
    relevance: string;
    favorable: boolean;
    factualSimilarity: "HIGH" | "MEDIUM" | "LOW";
    verificationStatus: VerificationStatus;
    distinguishingFactors?: string[];
  }>;
  circuitSplits: string[];
  recommendedCitations: string[];
}

// ============================================================
// CITATION VERIFICATION AGENT
// ============================================================

export interface CitationVerificationOutput {
  verifiedCitations: Array<{
    citation: string;
    status: "CONFIRMED" | "UNCONFIRMED" | "OVERRULED" | "SUPERSEDED";
    shepardSignal?: string;
    notes: string;
  }>;
  statuteAlerts: Array<{
    statuteSection: string;
    alert: string;
    amendmentDate?: string;
  }>;
}

// ============================================================
// FACT GATHERING AGENT
// ============================================================

export interface FactGatheringOutput {
  timeline: Array<{
    timestamp: string;
    event: string;
    source: "CLIENT" | "DOCUMENT" | "WITNESS";
    confidence: ConfidenceLevel;
  }>;
  witnesses: Array<{
    name: string;
    contactInfo: string;
    relationship: string;
    observedEvents: string[];
  }>;
  evidenceInventory: Array<{
    description: string;
    type: "PHYSICAL" | "DIGITAL" | "DOCUMENTARY" | "TESTIMONIAL";
    location: string;
    preservationStatus: string;
  }>;
  sceneDescription: string;
}

// ============================================================
// RIGHTS VIOLATION SCANNER
// ============================================================

export interface RightsViolationOutput {
  violations: Array<{
    id: string;
    amendment: "4TH" | "5TH" | "6TH" | "14TH";
    category: string;
    description: string;
    confidence: ConfidenceLevel;
    supportingFacts: string[];
  }>;
  discrepancyReport: Array<{
    topic: string;
    officerAccount: string;
    clientAccount: string;
    significance: "CRITICAL" | "NOTABLE" | "MINOR";
  }>;
  suppressionViability: {
    score: number; // 0-100
    confidence: ConfidenceLevel;
    basis: string;
    risks: string[];
  };
}

// ============================================================
// COLLATERAL CONSEQUENCES AGENT
// ============================================================

export interface CollateralConsequencesOutput {
  consequences: Array<{
    category: "IMMIGRATION" | "EMPLOYMENT" | "HOUSING" | "EDUCATION" | "FAMILY" | "CIVIL_RIGHTS";
    description: string;
    severity: "SEVERE" | "MODERATE" | "MINOR";
    chargeSpecific: boolean;
    affectsPleaStrategy: boolean;
  }>;
  padillaFlag: boolean;
  pleaStrategyImpact: string;
}

// ============================================================
// PERSONAL CIRCUMSTANCES AGENT
// ============================================================

export interface PersonalCircumstancesOutput {
  bailProfile: {
    communityTies: string[];
    flightRiskFactors: string[];
    recommendation: string;
  };
  mitigationNarrative: string;
  diversionEligibility: Array<{
    program: string;
    eligible: boolean;
    basis: string;
  }>;
  treatmentNeeds: string[];
}

// ============================================================
// MOTION DRAFTER AGENT
// ============================================================

export interface MotionDrafterOutput {
  motions: Array<{
    id: string;
    type: "SUPPRESS" | "DISMISS" | "BAIL_REDUCTION" | "DISCOVERY" | "LIMINE" | "OTHER";
    title: string;
    draft: string; // Full motion text
    status: "DRAFT";
    filingDeadline: string | null;
    supportingAuthority: string[];
  }>;
}

// ============================================================
// BRADY COMPLIANCE AGENT
// ============================================================

export interface BradyAnalysisOutput {
  gaps: Array<{
    id: string;
    category: "MISSING_REPORT" | "MISSING_FORENSIC" | "GIGLIO" | "CI_FILE" | "INCONSISTENT_STATEMENT" | "OTHER";
    description: string;
    expectedEvidence: string;
    basis: string;
  }>;
  giglioChecklist: Array<{
    officer: string;
    disciplinaryRecordRequested: boolean;
    status: string;
  }>;
  draftDemandLetter: string;
}

// ============================================================
// PLEA/TRIAL ASSESSMENT AGENT
// ============================================================

export interface PleaTrialOutput {
  pleaScenario: {
    charges: string[];
    sentencingRange: string;
    collateralConsequences: string[];
  };
  trialScenario: {
    charges: string[];
    acquittalProbability: number;
    sentencingIfConvicted: string;
    collateralConsequences: string[];
  };
  comparisonMatrix: Record<string, { plea: string; trial: string }>;
  riskFactors: string[];
  recommendation: string; // Always prefixed with "DECISION SUPPORT ONLY"
}

// ============================================================
// SENTENCING & MITIGATION AGENT
// ============================================================

export interface SentencingOutput {
  guidelineRange: {
    minimumMonths: number;
    maximumMonths: number;
    offenseLevel: string;
    criminalHistoryCategory: string;
  };
  departureArguments: Array<{
    direction: "DOWNWARD" | "UPWARD";
    basis: string;
    strength: ConfidenceLevel;
  }>;
  mitigationNarrative: string;
  alternatives: Array<{
    type: string;
    description: string;
    eligibility: string;
  }>;
  comparableSentences: Array<{
    caseSummary: string;
    sentence: string;
    similarity: string;
  }>;
  memoFramework: string;
}
