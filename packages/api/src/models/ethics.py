"""Data models for the Ethics & Compliance Monitor.

Supports the four enforcement pillars plus a cross-cutting hallucination detector:
1. Privilege Protection — attorney-client privilege, data siloing, encryption status
2. UPL Boundary — unauthorized practice of law detection, disclaimer enforcement
3. Bias Audit — racial, socioeconomic, and other bias detection in outputs
4. Competence Floor — confidence thresholds, low-confidence flagging
5. Hallucination Detection — catches fabricated citations, statutes, and facts
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EthicalCategory(str, Enum):
    """Categories of ethical flags raised by the monitor."""

    PRIVILEGE = "PRIVILEGE"
    UPL = "UPL"
    BIAS = "BIAS"
    COMPETENCE = "COMPETENCE"
    CANDOR = "CANDOR"
    IAC = "IAC"  # Ineffective Assistance of Counsel risk
    HALLUCINATION = "HALLUCINATION"


class FlagPriority(str, Enum):
    """Priority levels — determines merge decision in the Orchestrator."""

    CRITICAL = "CRITICAL"  # Hard block — output NOT merged
    HIGH = "HIGH"  # Merged with flag — attorney review required
    MEDIUM = "MEDIUM"  # Merged and logged
    LOW = "LOW"  # Logged only


class BiasCategory(str, Enum):
    """Types of bias the monitor scans for."""

    RACIAL = "RACIAL"
    SOCIOECONOMIC = "SOCIOECONOMIC"
    GENDER = "GENDER"
    AGE = "AGE"
    GEOGRAPHIC = "GEOGRAPHIC"
    DISABILITY = "DISABILITY"


class PrivilegeViolationType(str, Enum):
    """Types of privilege protection violations."""

    CLIENT_DATA_LEAK = "CLIENT_DATA_LEAK"
    MISSING_ENCRYPTION_FLAG = "MISSING_ENCRYPTION_FLAG"
    MISSING_PRIVILEGE_DISCLAIMER = "MISSING_PRIVILEGE_DISCLAIMER"
    TRAINING_DATA_EXPOSURE = "TRAINING_DATA_EXPOSURE"
    MISSING_ATTORNEY_REVIEW_DISCLAIMER = "MISSING_ATTORNEY_REVIEW_DISCLAIMER"


# ---------------------------------------------------------------------------
# Core flag model
# ---------------------------------------------------------------------------


class EthicalFlag(BaseModel):
    """A single ethical or compliance concern raised by the monitor."""

    id: str
    agent_source: str
    category: str  # EthicalCategory value — kept as str for JSON compat
    priority: str  # FlagPriority value
    description: str
    blocked: bool = False
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    resolution: str | None = None


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


class AuditEntry(BaseModel):
    """An entry in the system-wide audit log."""

    id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent_id: str
    action: str
    details: dict = Field(default_factory=dict)
    ethical_check: bool = False


# ---------------------------------------------------------------------------
# Pillar 1: Privilege Protection
# ---------------------------------------------------------------------------


class PrivilegeCheckResult(BaseModel):
    """Result of a privilege-protection scan on a single agent output."""

    agent_id: str
    violations: list[PrivilegeViolationDetail] = Field(default_factory=list)
    privileged_content_detected: bool = False
    encryption_verified: bool = False
    privilege_disclaimer_present: bool = False


class PrivilegeViolationDetail(BaseModel):
    """Detail record for a single privilege violation."""

    violation_type: str  # PrivilegeViolationType value
    description: str
    field_path: str | None = None  # dot-path to offending field


# Forward-ref update so PrivilegeCheckResult can reference PrivilegeViolationDetail
PrivilegeCheckResult.model_rebuild()


# ---------------------------------------------------------------------------
# Pillar 2: UPL Boundary
# ---------------------------------------------------------------------------


class UPLCheckResult(BaseModel):
    """Result of a UPL (unauthorized practice of law) scan."""

    agent_id: str
    is_client_facing: bool
    violations: list[UPLViolationDetail] = Field(default_factory=list)
    disclaimer_present: bool = False


class UPLViolationDetail(BaseModel):
    """Detail record for a single UPL violation."""

    phrase_matched: str
    context_snippet: str  # surrounding text for review
    description: str


UPLCheckResult.model_rebuild()


# ---------------------------------------------------------------------------
# Pillar 3: Bias Audit
# ---------------------------------------------------------------------------


class BiasIndicator(BaseModel):
    """A single detected bias signal."""

    bias_type: str  # BiasCategory value
    description: str
    evidence: str  # the text or data that triggered the signal
    severity: str  # FlagPriority value — how severe the bias concern is


class BiasAuditResult(BaseModel):
    """Result of a bias audit on an agent output."""

    agent_id: str
    indicators: list[BiasIndicator] = Field(default_factory=list)
    demographic_terms_found: list[str] = Field(default_factory=list)
    recommendation: str = ""  # action recommendation for the attorney


# ---------------------------------------------------------------------------
# Pillar 4: Competence Floor
# ---------------------------------------------------------------------------


class CompetenceCheckResult(BaseModel):
    """Result of a competence-floor check on an agent output."""

    agent_id: str
    confidence_level: str  # ConfidenceLevel value
    confidence_value: float | None = None
    below_threshold: bool = False
    missing_required_fields: list[str] = Field(default_factory=list)
    review_required: bool = False


# ---------------------------------------------------------------------------
# Pillar 5: Hallucination Detection
# ---------------------------------------------------------------------------


class HallucinationIndicator(BaseModel):
    """A single hallucination signal detected in an agent output."""

    indicator_type: str  # e.g. "FABRICATED_CITATION", "INVALID_STATUTE", "PHANTOM_CASE"
    description: str
    evidence: str  # the suspect text
    field_path: str | None = None  # dot-path to the offending field
    severity: str  # FlagPriority value


class HallucinationCheckResult(BaseModel):
    """Result of hallucination detection on an agent output."""

    agent_id: str
    indicators: list[HallucinationIndicator] = Field(default_factory=list)
    suspect_citations: list[str] = Field(default_factory=list)
    suspect_statutes: list[str] = Field(default_factory=list)
    fabrication_risk: str = "LOW"  # LOW / MEDIUM / HIGH / CRITICAL


# ---------------------------------------------------------------------------
# Composite ethics review result
# ---------------------------------------------------------------------------


class EthicsReviewResult(BaseModel):
    """Full ethics review result combining all pillars."""

    agent_id: str
    flags: list[EthicalFlag] = Field(default_factory=list)
    blocked: bool = False

    # Per-pillar detail (optional — populated when the check runs)
    privilege_check: PrivilegeCheckResult | None = None
    upl_check: UPLCheckResult | None = None
    bias_audit: BiasAuditResult | None = None
    competence_check: CompetenceCheckResult | None = None
    hallucination_check: HallucinationCheckResult | None = None

    audit_entries: list[AuditEntry] = Field(default_factory=list)
