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
import { mapCaseDetailToCaseState } from "./mappers";

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

  const headers: Record<string, string> = {
    "X-Attorney-Id": process.env.NEXT_PUBLIC_ATTORNEY_ID || "attorney_001",
  };

  // Only set Content-Type for JSON requests (not FormData)
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(url, {
    ...options,
    headers: {
      ...headers,
      ...options.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, error.detail || "Request failed");
  }

  return res.json() as Promise<T>;
}

// --- In-memory cache for CaseDetail to avoid redundant fetches ---

const caseDetailCache = new Map<
  string,
  { data: CaseDetail; fetchedAt: number }
>();
const CACHE_TTL_MS = 3000; // 3 seconds

async function getCaseCached(caseId: string): Promise<CaseDetail> {
  const cached = caseDetailCache.get(caseId);
  const now = Date.now();
  if (cached && now - cached.fetchedAt < CACHE_TTL_MS) {
    return cached.data;
  }
  const data = await apiFetch<CaseDetail>(`/api/v1/cases/${caseId}`);
  caseDetailCache.set(caseId, { data, fetchedAt: now });
  return data;
}

/** Invalidate the cache for a case (call after mutations). */
export function invalidateCaseCache(caseId: string): void {
  caseDetailCache.delete(caseId);
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

  return apiFetch<UploadResponse>("/api/v1/upload", {
    method: "POST",
    body: formData,
  });
}

// --- Cases ---

async function listCases(): Promise<CaseSummary[]> {
  return apiFetch<CaseSummary[]>("/api/v1/cases");
}

async function getCase(caseId: string): Promise<CaseDetail> {
  return getCaseCached(caseId);
}

async function getCaseStatus(caseId: string): Promise<CaseStatusResponse> {
  return apiFetch<CaseStatusResponse>(`/api/v1/cases/${caseId}/status`);
}

async function getCaseState(caseId: string): Promise<CaseState> {
  const detail = await getCaseCached(caseId);
  return mapCaseDetailToCaseState(detail);
}

// --- Agent Outputs (extracted from cached CaseDetail) ---

async function getMotions(caseId: string): Promise<MotionDrafterOutput> {
  const detail = await getCaseCached(caseId);
  if (!detail.draft_motions) {
    return { motions: [] };
  }
  return detail.draft_motions.data;
}

async function getPleaTrialAssessment(caseId: string): Promise<PleaTrialOutput | null> {
  const detail = await getCaseCached(caseId);
  return detail.plea_trial_assessment?.data ?? null;
}

async function getSentencingAnalysis(caseId: string): Promise<SentencingOutput | null> {
  const detail = await getCaseCached(caseId);
  return detail.sentencing_analysis?.data ?? null;
}

async function getBradyAnalysis(caseId: string): Promise<BradyAnalysisOutput | null> {
  const detail = await getCaseCached(caseId);
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
  invalidateCaseCache(caseId);
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
  invalidateCaseCache(caseId);
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
