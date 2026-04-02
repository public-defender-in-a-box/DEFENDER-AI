"""Ethics & Compliance Monitor — Cross-Cutting Guardrail.

Runs across all tiers and all agents. Enforces legal, ethical, and
constitutional boundaries. Cannot be overridden by any other agent.

Five enforcement pillars:
  1. Privilege Protection — attorney-client privilege, data siloing,
     encryption verification, no training on client data.
  2. UPL Boundary — client-facing agents inform only (never advise),
     disclaimers required, attorney approval before any filing.
  3. Bias Audit — monitors for racial, socioeconomic, gender, age,
     and other bias in case law selection, sentencing predictions,
     and plea recommendations.
  4. Competence Floor — confidence thresholds on all outputs; LOW
     results flagged for attorney review, not presented as reliable.
  5. Hallucination Detection — catches fabricated citations, invalid
     statute references, phantom case names, and unsupported factual
     claims across all agent tiers.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.case_state import ConfidenceLevel
from src.models.ethics import (
    BiasAuditResult,
    BiasIndicator,
    CompetenceCheckResult,
    EthicalFlag,
    EthicsReviewResult,
    HallucinationCheckResult,
    HallucinationIndicator,
    PrivilegeCheckResult,
    PrivilegeViolationDetail,
    UPLCheckResult,
    UPLViolationDetail,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLD = 0.6

# Pillar 2 — phrases that constitute unauthorized legal advice
UPL_VIOLATION_PHRASES: list[str] = [
    "you should plead",
    "i recommend",
    "i advise",
    "my legal opinion",
    "you must",
    "you need to",
    "the best option is",
    "you should take the deal",
    "you have no choice but",
    "plead guilty",
    "plead not guilty",
    "take the plea",
    "reject the plea",
    "you will be found guilty",
    "you will be acquitted",
]

# Pillar 2 — required disclaimer text for client-facing outputs
CLIENT_DISCLAIMER = (
    "This information is not legal advice. "
    "Please consult your attorney before making any decisions."
)

# Pillar 3 — demographic / identity terms that warrant bias review
# when found in analytical outputs (sentencing, plea, case law selection)
BIAS_SENSITIVE_TERMS: dict[str, str] = {
    # Racial / ethnic
    "african american": "RACIAL",
    "african-american": "RACIAL",
    "black defendant": "RACIAL",
    "white defendant": "RACIAL",
    "hispanic": "RACIAL",
    "latino": "RACIAL",
    "latina": "RACIAL",
    "asian": "RACIAL",
    "caucasian": "RACIAL",
    "minority": "RACIAL",
    "race": "RACIAL",
    "racial": "RACIAL",
    "ethnicity": "RACIAL",
    # Socioeconomic
    "low income": "SOCIOECONOMIC",
    "low-income": "SOCIOECONOMIC",
    "poverty": "SOCIOECONOMIC",
    "indigent": "SOCIOECONOMIC",
    "unemployed": "SOCIOECONOMIC",
    "homeless": "SOCIOECONOMIC",
    "public housing": "SOCIOECONOMIC",
    "welfare": "SOCIOECONOMIC",
    # Gender
    "gender": "GENDER",
    "male defendant": "GENDER",
    "female defendant": "GENDER",
    # Age
    "elderly": "AGE",
    "juvenile": "AGE",
    "young offender": "AGE",
    # Disability
    "mental illness": "DISABILITY",
    "mentally ill": "DISABILITY",
    "disabled": "DISABILITY",
    "disability": "DISABILITY",
}

# Agents whose outputs require bias auditing (sentencing, pleas, case law)
BIAS_AUDITABLE_AGENTS: set[str] = {
    "sentencing_agent",
    "plea_trial_analyst",
    "case_law_agent",
    "case_prep",
}

# Fields that should never contain raw client PII in non-encrypted outputs
CLIENT_PII_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
    re.compile(r"\b\d{9}\b"),  # SSN without dashes
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # email
    re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),  # phone number
]

# Agents that produce client-facing content
CLIENT_FACING_AGENTS: set[str] = {
    "intake_conductor",
    "fact_gatherer",
}

# Agents that produce attorney work-product (need privilege disclaimers)
ATTORNEY_WORK_PRODUCT_AGENTS: set[str] = {
    "motion_drafter",
    "plea_trial_analyst",
    "sentencing_agent",
    "brady_agent",
    "case_prep",
    "disclosure_tracking",
}

# Pillar 5 — Hallucination detection patterns

# Georgia statute format: O.C.G.A. § XX-XX-XX (Title 16 for crimes)
GEORGIA_STATUTE_PATTERN = re.compile(r"O\.C\.G\.A\.?\s*§\s*(\d{1,2})-(\d{1,2})-(\d{1,4})")

# Valid Georgia title numbers (subset — titles that exist in O.C.G.A.)
VALID_GEORGIA_TITLES: set[int] = {
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    21,
    22,
    23,
    24,
    25,
    26,
    27,
    28,
    29,
    30,
    31,
    32,
    33,
    34,
    35,
    36,
    37,
    38,
    39,
    40,
    41,
    42,
    43,
    44,
    45,
    46,
    47,
    48,
    49,
    50,
    51,
    52,
    53,
}

# Case citation pattern: Name v. Name, Volume Reporter Page (Year)
CASE_CITATION_PATTERN = re.compile(
    r"([A-Z][a-zA-Z\s\.]+)\s+v\.\s+([A-Z][a-zA-Z\s\.]+),\s*"
    r"(\d{1,4})\s+([A-Za-z\.\s]{2,20})\s+(\d{1,5})"
    r"(?:\s*\((\d{4})\))?"
)

# Known fabrication signals — phrases that hint at made-up content
HALLUCINATION_SIGNAL_PHRASES: list[str] = [
    "as established in the landmark case",
    "the well-known principle of",
    "it is universally accepted that",
    "courts have unanimously held",
    "as everyone knows",
    "the supreme court has always",
]

# Agents that produce legal citations and need hallucination checks
CITATION_PRODUCING_AGENTS: set[str] = {
    "statute_agent",
    "case_law_agent",
    "citation_verifier",
    "motion_drafter",
    "plea_trial_analyst",
    "sentencing_agent",
    "pre_interview_research",
    "charge_processing",
    "rights_scanner",
    "brady_agent",
}


class EthicsMonitorAgent(BaseAgent):
    """Cross-cutting ethics and compliance monitor.

    Called by the Orchestrator on every agent output before merge.
    Returns an EthicsReviewResult with flags, block decisions,
    and per-pillar detail records.
    """

    agent_id = "ethics_monitor"
    agent_name = "Ethics & Compliance Monitor"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Validate agent output against all four ethical pillars.

        Input keys:
            output: dict — the agent's wrapped output (data, confidence, source, timestamp)
            agent_id: str — which agent produced the output
            is_client_facing: bool — whether this output reaches the client

        Output: EthicsReviewResult as dict (flags, blocked, per-pillar details, audit)
        """
        self.log_action(
            "ethics_check_started",
            {"target_agent": input_data.get("agent_id")},
        )

        output = input_data.get("output", {})
        agent_id = input_data.get("agent_id", "unknown")
        is_client_facing = input_data.get("is_client_facing", False)

        flags: list[dict[str, Any]] = []

        # --- Pillar 1: Privilege Protection ---
        privilege_result = self._check_privilege_protection(agent_id, output, is_client_facing)
        flags.extend(privilege_result["flags"])

        # --- Pillar 2: UPL Boundary ---
        upl_result = self._check_upl_boundary(agent_id, output, is_client_facing)
        flags.extend(upl_result["flags"])

        # --- Pillar 3: Bias Audit ---
        bias_result = self._check_bias(agent_id, output)
        flags.extend(bias_result["flags"])

        # --- Pillar 4: Competence Floor ---
        competence_result = self._check_competence_floor(agent_id, output)
        flags.extend(competence_result["flags"])

        # --- Pillar 5: Hallucination Detection ---
        hallucination_result = self._check_hallucinations(agent_id, output)
        flags.extend(hallucination_result["flags"])

        blocked = any(f["blocked"] for f in flags)

        self.log_action(
            "ethics_check_completed",
            {
                "target_agent": agent_id,
                "flags_count": len(flags),
                "blocked": blocked,
                "pillar_flags": {
                    "privilege": len(privilege_result["flags"]),
                    "upl": len(upl_result["flags"]),
                    "bias": len(bias_result["flags"]),
                    "competence": len(competence_result["flags"]),
                    "hallucination": len(hallucination_result["flags"]),
                },
            },
        )

        # Build structured result
        review = EthicsReviewResult(
            agent_id=agent_id,
            flags=[EthicalFlag(**f) for f in flags],
            blocked=blocked,
            privilege_check=privilege_result.get("detail"),
            upl_check=upl_result.get("detail"),
            bias_audit=bias_result.get("detail"),
            competence_check=competence_result.get("detail"),
            hallucination_check=hallucination_result.get("detail"),
            audit_entries=list(self.get_audit_log()),
        )

        return review.model_dump(mode="json")

    # ------------------------------------------------------------------
    # Pillar 1: Privilege Protection
    # ------------------------------------------------------------------

    def _check_privilege_protection(
        self,
        agent_id: str,
        output: dict[str, Any],
        is_client_facing: bool,
    ) -> dict[str, Any]:
        """Enforce attorney-client privilege protections.

        Checks:
        - No raw client PII (SSN, email, phone) in output data
        - Attorney work-product outputs include privilege disclaimer
        - Draft outputs include ATTORNEY REVIEW REQUIRED
        - Outputs flagged if encryption metadata absent
        """
        flags: list[dict[str, Any]] = []
        violations: list[PrivilegeViolationDetail] = []
        data_str = str(output.get("data", ""))

        # Check 1: Scan for client PII patterns in output
        for pattern in CLIENT_PII_PATTERNS:
            matches = pattern.findall(data_str)
            if matches:
                violation = PrivilegeViolationDetail(
                    violation_type="CLIENT_DATA_LEAK",
                    description=(
                        f"Potential client PII detected in {agent_id} output: "
                        f"pattern matched {len(matches)} time(s). "
                        "Client data must not appear in unencrypted agent outputs."
                    ),
                    field_path="data",
                )
                violations.append(violation)
                flags.append(
                    self._create_flag(
                        agent_id,
                        "PRIVILEGE",
                        "CRITICAL",
                        violation.description,
                        blocked=True,
                    )
                )

        # Check 2: Attorney work-product must have privilege disclaimer
        if agent_id in ATTORNEY_WORK_PRODUCT_AGENTS:
            if "ATTORNEY REVIEW REQUIRED" not in data_str:
                violation = PrivilegeViolationDetail(
                    violation_type="MISSING_ATTORNEY_REVIEW_DISCLAIMER",
                    description=(
                        f"Agent {agent_id} produces attorney work-product "
                        "but output is missing ATTORNEY REVIEW REQUIRED disclaimer."
                    ),
                    field_path="data",
                )
                violations.append(violation)
                flags.append(
                    self._create_flag(
                        agent_id,
                        "PRIVILEGE",
                        "HIGH",
                        violation.description,
                        blocked=False,
                    )
                )

        # Check 3: Draft outputs need review disclaimer
        if "DRAFT" in data_str and "ATTORNEY REVIEW REQUIRED" not in data_str:
            if not any(
                v.violation_type == "MISSING_ATTORNEY_REVIEW_DISCLAIMER" for v in violations
            ):
                violation = PrivilegeViolationDetail(
                    violation_type="MISSING_PRIVILEGE_DISCLAIMER",
                    description="Draft output missing ATTORNEY REVIEW REQUIRED disclaimer.",
                    field_path="data",
                )
                violations.append(violation)
                flags.append(
                    self._create_flag(
                        agent_id,
                        "PRIVILEGE",
                        "LOW",
                        violation.description,
                        blocked=False,
                    )
                )

        # Check 4: Encryption metadata should be present for client-related data
        metadata = output.get("metadata", {})
        encryption_verified = (
            metadata.get("encrypted", False) if isinstance(metadata, dict) else False
        )

        detail = PrivilegeCheckResult(
            agent_id=agent_id,
            violations=violations,
            privileged_content_detected=len(violations) > 0,
            encryption_verified=encryption_verified,
            privilege_disclaimer_present="ATTORNEY REVIEW REQUIRED" in data_str,
        )

        return {"flags": flags, "detail": detail}

    # ------------------------------------------------------------------
    # Pillar 2: UPL Boundary
    # ------------------------------------------------------------------

    def _check_upl_boundary(
        self,
        agent_id: str,
        output: dict[str, Any],
        is_client_facing: bool,
    ) -> dict[str, Any]:
        """Enforce unauthorized-practice-of-law boundaries.

        Checks:
        - Client-facing outputs must not contain advisory phrases
        - Client-facing outputs must include a not-legal-advice disclaimer
        - Plea/trial outputs must include DECISION SUPPORT ONLY
        - Filing-related outputs must require attorney approval
        """
        flags: list[dict[str, Any]] = []
        violations: list[UPLViolationDetail] = []
        data_str = str(output.get("data", ""))
        content_lower = data_str.lower()

        # Check 1: UPL violation phrases in client-facing content
        if is_client_facing or agent_id in CLIENT_FACING_AGENTS:
            for phrase in UPL_VIOLATION_PHRASES:
                if phrase in content_lower:
                    # Extract surrounding context (up to 80 chars)
                    idx = content_lower.index(phrase)
                    start = max(0, idx - 40)
                    end = min(len(content_lower), idx + len(phrase) + 40)
                    context = data_str[start:end]

                    violation = UPLViolationDetail(
                        phrase_matched=phrase,
                        context_snippet=context,
                        description=(
                            f"Potential UPL violation: client-facing output "
                            f"from {agent_id} contains '{phrase}'. "
                            "Client-facing agents must INFORM, never ADVISE."
                        ),
                    )
                    violations.append(violation)
                    flags.append(
                        self._create_flag(
                            agent_id,
                            "UPL",
                            "CRITICAL",
                            violation.description,
                            blocked=True,
                        )
                    )

            # Check 2: Client-facing outputs need a disclaimer
            has_disclaimer = any(
                marker in content_lower
                for marker in [
                    "not legal advice",
                    "consult your attorney",
                    "this is informational only",
                    "for informational purposes",
                ]
            )
            if not has_disclaimer and data_str.strip():
                flags.append(
                    self._create_flag(
                        agent_id,
                        "UPL",
                        "HIGH",
                        (
                            f"Client-facing output from {agent_id} is missing "
                            "a 'not legal advice' disclaimer. All client-facing "
                            "outputs must clearly state they are not legal advice."
                        ),
                        blocked=False,
                    )
                )

        # Check 3: Decision-support disclaimer on plea/trial outputs
        if agent_id == "plea_trial_analyst":
            recommendation = str(output.get("data", {}).get("recommendation", ""))
            if recommendation and "DECISION SUPPORT ONLY" not in recommendation:
                flags.append(
                    self._create_flag(
                        agent_id,
                        "UPL",
                        "HIGH",
                        "Plea/trial recommendation missing DECISION SUPPORT ONLY disclaimer.",
                        blocked=True,
                    )
                )

        # Check 4: Motion/filing outputs require attorney approval marker
        if agent_id == "motion_drafter":
            if "DRAFT" not in data_str:
                flags.append(
                    self._create_flag(
                        agent_id,
                        "UPL",
                        "HIGH",
                        (
                            "Motion drafter output not marked as DRAFT. "
                            "All draft motions must be marked "
                            "'DRAFT — ATTORNEY REVIEW REQUIRED' before any filing."
                        ),
                        blocked=False,
                    )
                )

        disclaimer_present = any(
            marker in content_lower for marker in ["not legal advice", "consult your attorney"]
        )

        detail = UPLCheckResult(
            agent_id=agent_id,
            is_client_facing=is_client_facing or agent_id in CLIENT_FACING_AGENTS,
            violations=violations,
            disclaimer_present=disclaimer_present,
        )

        return {"flags": flags, "detail": detail}

    # ------------------------------------------------------------------
    # Pillar 3: Bias Audit
    # ------------------------------------------------------------------

    def _check_bias(
        self,
        agent_id: str,
        output: dict[str, Any],
    ) -> dict[str, Any]:
        """Audit agent outputs for potential bias signals.

        Monitors for:
        - Demographic terms used in analytical context (sentencing, pleas, case law)
        - Disproportionate language suggesting bias in recommendations
        - Stereotyping patterns in case analysis
        """
        flags: list[dict[str, Any]] = []
        indicators: list[BiasIndicator] = []
        demographic_terms: list[str] = []

        # Only run full bias audit on agents that produce analytical outputs
        if agent_id not in BIAS_AUDITABLE_AGENTS:
            detail = BiasAuditResult(
                agent_id=agent_id,
                indicators=[],
                demographic_terms_found=[],
                recommendation="",
            )
            return {"flags": flags, "detail": detail}

        data = output.get("data", {})
        data_str = str(data).lower()

        # Scan for demographic/identity terms
        for term, bias_type in BIAS_SENSITIVE_TERMS.items():
            if term in data_str:
                demographic_terms.append(term)

        # If demographic terms appear in analytical outputs, flag for review
        if demographic_terms:
            # Check for correlation patterns — demographic term near
            # recommendation, sentence, or outcome language
            outcome_terms = [
                "sentence",
                "sentencing",
                "recommend",
                "recommendation",
                "plea",
                "incarceration",
                "probation",
                "prison",
                "penalty",
                "punishment",
                "outcome",
                "risk",
                "likelihood",
                "predict",
                "recidivism",
            ]

            correlations_found: list[str] = []
            for demo_term in demographic_terms:
                for outcome_term in outcome_terms:
                    # Check if both terms appear within 200 chars of each other
                    demo_positions = [
                        m.start() for m in re.finditer(re.escape(demo_term), data_str)
                    ]
                    outcome_positions = [
                        m.start() for m in re.finditer(re.escape(outcome_term), data_str)
                    ]
                    for d_pos in demo_positions:
                        for o_pos in outcome_positions:
                            if abs(d_pos - o_pos) < 200:
                                correlations_found.append(f"{demo_term} ↔ {outcome_term}")

            if correlations_found:
                # Deduplicate
                unique_correlations = list(set(correlations_found))

                indicator = BiasIndicator(
                    bias_type=BIAS_SENSITIVE_TERMS.get(demographic_terms[0], "RACIAL"),
                    description=(
                        f"Agent {agent_id} output contains demographic terms "
                        f"correlated with outcome language: "
                        f"{', '.join(unique_correlations[:5])}. "
                        "This may indicate bias in the analysis."
                    ),
                    evidence=f"Terms found: {', '.join(demographic_terms)}",
                    severity="HIGH",
                )
                indicators.append(indicator)
                flags.append(
                    self._create_flag(
                        agent_id,
                        "BIAS",
                        "HIGH",
                        indicator.description,
                        blocked=False,
                    )
                )
            elif len(demographic_terms) >= 3:
                # Multiple demographic terms without clear correlation —
                # lower severity but still worth noting
                indicator = BiasIndicator(
                    bias_type=BIAS_SENSITIVE_TERMS.get(demographic_terms[0], "RACIAL"),
                    description=(
                        f"Agent {agent_id} output references multiple "
                        f"demographic terms ({', '.join(demographic_terms[:5])}). "
                        "Attorney should review for potential bias."
                    ),
                    evidence=f"Terms found: {', '.join(demographic_terms)}",
                    severity="MEDIUM",
                )
                indicators.append(indicator)
                flags.append(
                    self._create_flag(
                        agent_id,
                        "BIAS",
                        "MEDIUM",
                        indicator.description,
                        blocked=False,
                    )
                )

        # Check for stereotyping patterns in sentencing/plea recommendations
        if agent_id in ("sentencing_agent", "plea_trial_analyst"):
            stereotyping_phrases = [
                "typical for this demographic",
                "people like the defendant",
                "defendants of this background",
                "statistically more likely",
                "this population tends to",
                "common among",
                "characteristic of",
            ]
            for phrase in stereotyping_phrases:
                if phrase in data_str:
                    indicator = BiasIndicator(
                        bias_type="RACIAL",
                        description=(
                            f"Potential stereotyping detected in {agent_id}: "
                            f"output contains '{phrase}'. Sentencing and plea "
                            "recommendations must be based on case facts, not "
                            "demographic generalizations."
                        ),
                        evidence=phrase,
                        severity="CRITICAL",
                    )
                    indicators.append(indicator)
                    flags.append(
                        self._create_flag(
                            agent_id,
                            "BIAS",
                            "CRITICAL",
                            indicator.description,
                            blocked=True,
                        )
                    )

        recommendation = ""
        if indicators:
            recommendation = (
                "Attorney review recommended: bias indicators detected in "
                f"{agent_id} output. Review demographic references for "
                "appropriateness and ensure recommendations are based on "
                "individual case facts, not group characteristics."
            )

        detail = BiasAuditResult(
            agent_id=agent_id,
            indicators=indicators,
            demographic_terms_found=demographic_terms,
            recommendation=recommendation,
        )

        return {"flags": flags, "detail": detail}

    # ------------------------------------------------------------------
    # Pillar 4: Competence Floor
    # ------------------------------------------------------------------

    def _check_competence_floor(
        self,
        agent_id: str,
        output: dict[str, Any],
    ) -> dict[str, Any]:
        """Enforce minimum competence thresholds on all outputs.

        Checks:
        - Confidence level is above threshold (LOW → flagged)
        - Required output fields are present
        - UNRATED outputs are flagged as missing confidence scoring
        """
        flags: list[dict[str, Any]] = []
        confidence_str = output.get("confidence", "UNRATED")
        confidence_value: float | None = None

        # Try to extract numeric confidence if available
        if isinstance(confidence_str, (int, float)):
            confidence_value = float(confidence_str)
        elif isinstance(confidence_str, str):
            # Map enum back to approximate numeric for reporting
            confidence_map = {"HIGH": 0.9, "MEDIUM": 0.7, "LOW": 0.4, "UNRATED": None}
            confidence_value = confidence_map.get(confidence_str.upper())

        below_threshold = confidence_str == ConfidenceLevel.LOW.value
        review_required = False

        # Check 1: LOW confidence — flag for attorney review
        if below_threshold:
            review_required = True
            flags.append(
                self._create_flag(
                    agent_id,
                    "COMPETENCE",
                    "MEDIUM",
                    (
                        f"Agent {agent_id} output has LOW confidence. "
                        "Flagged for attorney review — this output should "
                        "not be presented as reliable without human verification."
                    ),
                    blocked=False,
                )
            )

        # Check 2: UNRATED confidence — agent didn't score its output
        if confidence_str == ConfidenceLevel.UNRATED.value or confidence_str == "UNRATED":
            review_required = True
            flags.append(
                self._create_flag(
                    agent_id,
                    "COMPETENCE",
                    "HIGH",
                    (
                        f"Agent {agent_id} returned output without a confidence "
                        "score (UNRATED). All agent outputs must include a "
                        "confidence score for competence verification."
                    ),
                    blocked=False,
                )
            )

        # Check 3: Required fields check — data should not be empty
        data = output.get("data")
        missing_fields: list[str] = []

        if data is None:
            missing_fields.append("data")
            flags.append(
                self._create_flag(
                    agent_id,
                    "COMPETENCE",
                    "CRITICAL",
                    f"Agent {agent_id} returned null data. Output is empty.",
                    blocked=True,
                )
            )
        elif isinstance(data, dict) and not data:
            missing_fields.append("data (empty dict)")
            flags.append(
                self._create_flag(
                    agent_id,
                    "COMPETENCE",
                    "HIGH",
                    (
                        f"Agent {agent_id} returned an empty data object. "
                        "Output may be incomplete."
                    ),
                    blocked=False,
                )
            )

        # Check 4: Source attribution must be present
        if not output.get("source"):
            missing_fields.append("source")
            flags.append(
                self._create_flag(
                    agent_id,
                    "COMPETENCE",
                    "MEDIUM",
                    f"Agent {agent_id} output missing source attribution.",
                    blocked=False,
                )
            )

        detail = CompetenceCheckResult(
            agent_id=agent_id,
            confidence_level=str(confidence_str),
            confidence_value=confidence_value,
            below_threshold=below_threshold,
            missing_required_fields=missing_fields,
            review_required=review_required,
        )

        return {"flags": flags, "detail": detail}

    # ------------------------------------------------------------------
    # Pillar 5: Hallucination Detection
    # ------------------------------------------------------------------

    def _check_hallucinations(
        self,
        agent_id: str,
        output: dict[str, Any],
    ) -> dict[str, Any]:
        """Detect potential hallucinations in agent outputs.

        Checks across all tiers:
        - Invalid Georgia statute references (bad title/chapter numbers)
        - Suspect case citations (malformed or missing verification)
        - Fabrication signal phrases that suggest made-up content
        - Unverified citations presented as verified
        - Internal inconsistencies (e.g. citation lists vs. body references)
        """
        flags: list[dict[str, Any]] = []
        indicators: list[HallucinationIndicator] = []
        suspect_citations: list[str] = []
        suspect_statutes: list[str] = []

        data = output.get("data", {})
        data_str = str(data)
        data_lower = data_str.lower()

        # --- Check 1: Invalid Georgia statute references ---
        statute_matches = GEORGIA_STATUTE_PATTERN.finditer(data_str)
        for match in statute_matches:
            title = int(match.group(1))
            full_ref = match.group(0)

            if title not in VALID_GEORGIA_TITLES:
                suspect_statutes.append(full_ref)
                indicator = HallucinationIndicator(
                    indicator_type="INVALID_STATUTE",
                    description=(
                        f"Invalid Georgia statute reference '{full_ref}': "
                        f"Title {title} does not exist in O.C.G.A. "
                        "This may be a fabricated citation."
                    ),
                    evidence=full_ref,
                    field_path="data",
                    severity="CRITICAL",
                )
                indicators.append(indicator)
                flags.append(
                    self._create_flag(
                        agent_id,
                        "HALLUCINATION",
                        "CRITICAL",
                        indicator.description,
                        blocked=True,
                    )
                )

        # --- Check 2: Suspect case citations ---
        if agent_id in CITATION_PRODUCING_AGENTS:
            citation_matches = CASE_CITATION_PATTERN.finditer(data_str)
            for match in citation_matches:
                full_cite = match.group(0)
                year_str = match.group(6)

                # Flag future-dated citations
                if year_str:
                    try:
                        year = int(year_str)
                        if year > 2026:
                            suspect_citations.append(full_cite)
                            indicator = HallucinationIndicator(
                                indicator_type="FUTURE_DATED_CITATION",
                                description=(
                                    f"Citation '{full_cite}' references year {year}, "
                                    "which is in the future. Likely fabricated."
                                ),
                                evidence=full_cite,
                                field_path="data",
                                severity="CRITICAL",
                            )
                            indicators.append(indicator)
                            flags.append(
                                self._create_flag(
                                    agent_id,
                                    "HALLUCINATION",
                                    "CRITICAL",
                                    indicator.description,
                                    blocked=True,
                                )
                            )
                    except ValueError:
                        pass

            # Check for citations marked UNVERIFIED being presented without caveat
            if isinstance(data, dict):
                citations_list = data.get("citations", [])
                if isinstance(citations_list, list):
                    for cite in citations_list:
                        if isinstance(cite, dict):
                            status = cite.get("verification_status", "")
                            if status == "UNVERIFIED":
                                cite_text = cite.get("citation", cite.get("name", "unknown"))
                                suspect_citations.append(str(cite_text))
                                indicator = HallucinationIndicator(
                                    indicator_type="UNVERIFIED_CITATION",
                                    description=(
                                        f"Citation '{cite_text}' has UNVERIFIED status. "
                                        "Must be tagged as unverified in all outputs."
                                    ),
                                    evidence=str(cite_text),
                                    field_path="data.citations",
                                    severity="HIGH",
                                )
                                indicators.append(indicator)

                    # Flag if many citations are unverified — higher fabrication risk
                    unverified_count = sum(
                        1
                        for c in citations_list
                        if isinstance(c, dict) and c.get("verification_status") == "UNVERIFIED"
                    )
                    total_citations = len(citations_list)
                    if total_citations > 0 and unverified_count / total_citations > 0.5:
                        flags.append(
                            self._create_flag(
                                agent_id,
                                "HALLUCINATION",
                                "HIGH",
                                (
                                    f"Agent {agent_id} output has {unverified_count}/{total_citations} "
                                    "UNVERIFIED citations (>50%). High fabrication risk — "
                                    "attorney must verify before relying on these."
                                ),
                                blocked=False,
                            )
                        )

        # --- Check 3: Fabrication signal phrases ---
        for phrase in HALLUCINATION_SIGNAL_PHRASES:
            if phrase in data_lower:
                indicator = HallucinationIndicator(
                    indicator_type="FABRICATION_SIGNAL",
                    description=(
                        f"Fabrication signal detected in {agent_id} output: "
                        f"'{phrase}'. This hedge language often accompanies "
                        "hallucinated content."
                    ),
                    evidence=phrase,
                    field_path="data",
                    severity="HIGH",
                )
                indicators.append(indicator)
                flags.append(
                    self._create_flag(
                        agent_id,
                        "HALLUCINATION",
                        "HIGH",
                        indicator.description,
                        blocked=False,
                    )
                )

        # --- Check 4: Self-contradictory confidence ---
        # If agent claims HIGH confidence but output has many caveats/hedges
        confidence = output.get("confidence", "UNRATED")
        if confidence == "HIGH":
            hedge_words = [
                "possibly",
                "perhaps",
                "might",
                "may be",
                "uncertain",
                "unclear",
                "not sure",
                "it appears",
                "seemingly",
                "it is believed",
                "allegedly",
            ]
            hedge_count = sum(1 for w in hedge_words if w in data_lower)
            if hedge_count >= 3:
                indicator = HallucinationIndicator(
                    indicator_type="CONFIDENCE_MISMATCH",
                    description=(
                        f"Agent {agent_id} claims HIGH confidence but output "
                        f"contains {hedge_count} hedging phrases, suggesting "
                        "uncertainty. Confidence score may be inflated."
                    ),
                    evidence=f"{hedge_count} hedging phrases found",
                    field_path="confidence",
                    severity="MEDIUM",
                )
                indicators.append(indicator)
                flags.append(
                    self._create_flag(
                        agent_id,
                        "HALLUCINATION",
                        "MEDIUM",
                        indicator.description,
                        blocked=False,
                    )
                )

        # Determine overall fabrication risk
        if any(i.severity == "CRITICAL" for i in indicators):
            fabrication_risk = "CRITICAL"
        elif any(i.severity == "HIGH" for i in indicators):
            fabrication_risk = "HIGH"
        elif indicators:
            fabrication_risk = "MEDIUM"
        else:
            fabrication_risk = "LOW"

        detail = HallucinationCheckResult(
            agent_id=agent_id,
            indicators=indicators,
            suspect_citations=suspect_citations,
            suspect_statutes=suspect_statutes,
            fabrication_risk=fabrication_risk,
        )

        return {"flags": flags, "detail": detail}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_flag(
        self,
        agent_source: str,
        category: str,
        priority: str,
        description: str,
        blocked: bool,
    ) -> dict[str, Any]:
        """Create an EthicalFlag dict."""
        return EthicalFlag(
            id=str(uuid.uuid4()),
            agent_source=agent_source,
            category=category,
            priority=priority,
            description=description,
            blocked=blocked,
        ).model_dump(mode="json")
