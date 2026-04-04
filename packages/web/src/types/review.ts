export type ReviewTier = "HIGH_STAKES" | "MEDIUM_STAKES" | "LOWER_STAKES";
export type ReviewStatus = "PENDING_REVIEW" | "IN_REVIEW" | "ATTORNEY_APPROVED";

export interface ReviewSection {
  sectionId: string;
  sectionTitle: string;
  tier: ReviewTier;
  status: ReviewStatus;
  annotation?: string;
  editsMade: boolean;
  comprehensionCheckPassed?: boolean;
}

export interface ComprehensionCheck {
  sectionId: string;
  question: string;
  expectedKeywords: string[];
}

// --- API request/response types ---

export interface AnnotationSubmission {
  text: string;
  agrees_with_system: boolean;
  reasoning: string;
}

export interface ComprehensionCheckResult {
  passed: boolean;
  feedback?: string;
}

export interface ReviewStatusResponse {
  case_id: string;
  sections: ReviewSection[];
}
