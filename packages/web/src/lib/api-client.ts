import type {
  CaseSummary,
  CaseDetail,
  CaseState,
  CaseStatusResponse,
  UploadResponse,
} from "@/types/case";
import type {
  MotionDrafterOutput,
  PleaTrialOutput,
  SentencingOutput,
  BradyAnalysisOutput,
} from "@/types/agents";
import type {
  AnnotationSubmission,
  ComprehensionCheckResult,
  ReviewStatusResponse,
} from "@/types/review";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// --- Core fetch wrapper ---

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${path}`;

  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Attorney-Id": process.env.NEXT_PUBLIC_ATTORNEY_ID || "attorney_001",
      ...options.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, error.detail || "Request failed");
  }

  return res.json() as Promise<T>;
}

// --- Upload ---

async function uploadDocument(
  file: File,
  documentType?: string,
  jurisdiction?: string
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (documentType) formData.append("document_type", documentType);
  if (jurisdiction) formData.append("jurisdiction", jurisdiction);

  const url = `${API_BASE}/api/v1/upload`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "X-Attorney-Id": process.env.NEXT_PUBLIC_ATTORNEY_ID || "attorney_001",
    },
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, error.detail || "Upload failed");
  }

  return res.json();
}

// --- Cases ---

async function listCases(): Promise<CaseSummary[]> {
  return apiFetch<CaseSummary[]>("/api/v1/cases");
}

async function getCase(caseId: string): Promise<CaseDetail> {
  return apiFetch<CaseDetail>(`/api/v1/cases/${caseId}`);
}

async function getCaseStatus(caseId: string): Promise<CaseStatusResponse> {
  return apiFetch<CaseStatusResponse>(`/api/v1/cases/${caseId}/status`);
}

async function getCaseState(caseId: string): Promise<CaseState> {
  return apiFetch<CaseState>(`/api/v1/cases/${caseId}`);
}

// --- Agent Outputs ---

async function getMotions(caseId: string): Promise<MotionDrafterOutput> {
  const detail = await getCase(caseId);
  if (!detail.draft_motions) {
    return { motions: [] };
  }
  return detail.draft_motions.data;
}

async function getPleaTrialAssessment(caseId: string): Promise<PleaTrialOutput | null> {
  const detail = await getCase(caseId);
  return detail.plea_trial_assessment?.data ?? null;
}

async function getSentencingAnalysis(caseId: string): Promise<SentencingOutput | null> {
  const detail = await getCase(caseId);
  return detail.sentencing_analysis?.data ?? null;
}

async function getBradyAnalysis(caseId: string): Promise<BradyAnalysisOutput | null> {
  const detail = await getCase(caseId);
  return detail.brady_analysis?.data ?? null;
}

// --- Attorney Review ---

async function getReviewStatus(caseId: string): Promise<ReviewStatusResponse> {
  return apiFetch<ReviewStatusResponse>(`/api/v1/cases/${caseId}/review`);
}

async function submitAnnotation(
  caseId: string,
  sectionId: string,
  annotation: AnnotationSubmission
): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(
    `/api/v1/cases/${caseId}/review/${sectionId}/annotate`,
    {
      method: "POST",
      body: JSON.stringify(annotation),
    }
  );
}

async function approveSection(
  caseId: string,
  sectionId: string
): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(
    `/api/v1/cases/${caseId}/review/${sectionId}/approve`,
    {
      method: "POST",
    }
  );
}

async function submitComprehensionCheck(
  caseId: string,
  sectionId: string,
  answer: string
): Promise<ComprehensionCheckResult> {
  return apiFetch<ComprehensionCheckResult>(
    `/api/v1/cases/${caseId}/review/${sectionId}/comprehension`,
    {
      method: "POST",
      body: JSON.stringify({ answer }),
    }
  );
}

// --- Export namespaced API object ---

export const api = {
  upload: {
    document: uploadDocument,
  },
  cases: {
    list: listCases,
    get: getCase,
    status: getCaseStatus,
    state: getCaseState,
  },
  agents: {
    motions: getMotions,
    pleaTrial: getPleaTrialAssessment,
    sentencing: getSentencingAnalysis,
    brady: getBradyAnalysis,
  },
  review: {
    status: getReviewStatus,
    annotate: submitAnnotation,
    approve: approveSection,
    comprehensionCheck: submitComprehensionCheck,
  },
} as const;
