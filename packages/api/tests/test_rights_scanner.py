"""Tests for the Rights Violation Scanner agent and models."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.models.rights import (
    DiscrepancyItem,
    EighthAmendmentAnalysis,
    MirandaAnalysis,
    RightsScannerInput,
    RightsScannerOutput,
    RightsViolation,
    SearchAnalysis,
    SixthAmendmentAnalysis,
    SuppressionViability,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_ARREST_REPORT = """
ATLANTA POLICE DEPARTMENT — ARREST REPORT
Case No: 2024-APD-04521
Date: January 15, 2024, 2:30 AM
Location: Peachtree St and Andrew Young International Blvd, Atlanta, GA

Arresting Officer: Officer James Smith, Badge #4521, Zone 3
Witness Officer: Officer Maria Garcia, Badge #3847, Zone 3

NARRATIVE:
At approximately 2:15 AM, I observed the defendant JOHN DOE standing near the
intersection appearing nervous and looking around repeatedly. Based on my
training and experience, I approached the defendant and asked if I could speak
with him. The defendant agreed.

I asked the defendant if he had anything illegal on his person. The defendant
stated "no." I then asked if I could search the defendant's person and
backpack. The defendant verbally consented to the search.

Upon searching the defendant's backpack, I located a small plastic bag
containing a white powdery substance in the front pocket. Field testing
confirmed the substance to be cocaine, weighing approximately 2.3 grams.

The defendant was placed under arrest at 2:25 AM. Miranda rights were read
from the standard APD card at 2:30 AM. The defendant stated he understood
his rights.

The defendant was transported to Fulton County Jail for processing.
Booking completed at 4:15 AM.
"""

SAMPLE_CLIENT_NARRATIVE = """
I was walking home from work — I work the late shift at the restaurant on
Peachtree. Two officers pulled up in their car and got out. They didn't ask
if they could talk to me, they told me to stop and put my hands where they
could see them.

One officer asked me what I was doing out so late. I told him I was walking
home from work. He said I looked suspicious and asked if I had drugs on me.
I said no. He then said "we can do this the easy way or the hard way" and
told me to put my bag on the ground. I didn't feel like I had a choice.
He went through my whole bag.

They didn't read me my rights until we were at the station. When they were
putting me in the car, one officer asked me "whose cocaine is that?" and I
said "I don't know, it's not mine." They used that statement against me later.

I asked for a lawyer when we got to the station but the detective said I
could talk to one after they finished paperwork. They kept asking me questions
for about 30 minutes before a lawyer showed up.
"""

SAMPLE_OFFICER_CONDUCT = """
Officer James Smith — Badge #4521
- 3 prior excessive force complaints (2 dismissed, 1 sustained 2022)
- 1 prior complaint regarding consent-to-search procedures (pending)
"""


@pytest.fixture
def sample_arrest_report() -> str:
    return SAMPLE_ARREST_REPORT


@pytest.fixture
def sample_client_narrative() -> str:
    return SAMPLE_CLIENT_NARRATIVE


@pytest.fixture
def sample_officer_conduct() -> str:
    return SAMPLE_OFFICER_CONDUCT


@pytest.fixture
def sample_pass1_result() -> dict:
    """Simulated Pass 1 LLM output."""
    return {
        "violations": [
            {
                "id": "V001",
                "amendment": "4TH",
                "category": "COERCED_CONSENT",
                "description": "Consent language in report appears formulaic; "
                "officer has prior complaint regarding consent procedures.",
                "severity": "SIGNIFICANT",
                "confidence": 0.7,
                "supporting_facts": [
                    "Boilerplate consent language",
                    "Officer has prior consent complaint",
                ],
                "source": "ARREST_REPORT",
                "legal_standard": "Voluntariness of consent under Schneckloth v. Bustamonte",
                "relevant_case_law": [
                    "Schneckloth v. Bustamonte",
                    "Bumper v. North Carolina",
                ],
                "suppression_potential": "MEDIUM",
            },
            {
                "id": "V002",
                "amendment": "5TH",
                "category": "DELAYED_MIRANDA",
                "description": "Miranda administered 5 minutes after arrest. "
                "Questioning may have occurred before Miranda.",
                "severity": "MODERATE",
                "confidence": 0.6,
                "supporting_facts": [
                    "Arrest at 2:25 AM",
                    "Miranda at 2:30 AM",
                    "Gap of 5 minutes",
                ],
                "source": "ARREST_REPORT",
                "legal_standard": "Miranda v. Arizona — custodial interrogation",
                "relevant_case_law": ["Miranda v. Arizona"],
                "suppression_potential": "MEDIUM",
            },
        ],
        "miranda_analysis": {
            "miranda_given": True,
            "timing": "AFTER_QUESTIONING",
            "custodial": True,
            "statements_before_miranda": [],
            "statements_after_miranda": [],
            "waiver_validity": "UNKNOWN",
            "suppression_basis": "Miranda administered after arrest; unclear if questioning occurred before.",
        },
        "search_analysis": {
            "search_occurred": True,
            "warrant_present": False,
            "probable_cause_articulated": "Defendant appeared nervous",
            "consent_given": True,
            "consent_voluntariness": "QUESTIONABLE",
            "scope_exceeded": False,
            "exigent_circumstances_claimed": False,
            "plain_view_claimed": False,
            "search_incident_to_arrest": False,
            "vehicle_exception": False,
            "evidence_found": ["2.3 grams cocaine in backpack"],
            "suppression_basis": "Consent may not have been voluntary; "
            "nervous appearance alone is insufficient for reasonable suspicion.",
        },
        "sixth_amendment_analysis": {
            "counsel_requested": None,
            "counsel_provided": None,
            "counsel_denied_or_delayed": False,
            "lineup_conducted": False,
            "lineup_procedural_issues": [],
            "speedy_trial_concerns": "",
            "confrontation_issues": [],
        },
        "eighth_amendment_analysis": {
            "excessive_bail": None,
            "bail_amount": "",
            "bail_proportionality": "",
            "excessive_force": None,
            "force_description": "",
            "cruel_conditions": [],
        },
    }


@pytest.fixture
def sample_pass2_result() -> dict:
    """Simulated Pass 2 LLM output."""
    return {
        "additional_violations": [
            {
                "id": "CV001",
                "amendment": "4TH",
                "category": "COERCED_CONSENT",
                "description": "Client states officer said 'easy way or hard way', "
                "indicating coercion. Client felt no choice.",
                "severity": "CRITICAL",
                "confidence": 0.8,
                "supporting_facts": [
                    "Client reports officer threat",
                    "Client felt no choice",
                    "Contradicts voluntary consent in report",
                ],
                "source": "CLIENT_NARRATIVE",
                "legal_standard": "Schneckloth v. Bustamonte — totality of circumstances",
                "relevant_case_law": [
                    "Schneckloth v. Bustamonte",
                    "Bumper v. North Carolina",
                ],
                "suppression_potential": "HIGH",
            },
            {
                "id": "CV002",
                "amendment": "5TH",
                "category": "QUESTIONING_BEFORE_MIRANDA",
                "description": "Client reports being asked 'whose cocaine is that' "
                "before Miranda was read at the station.",
                "severity": "CRITICAL",
                "confidence": 0.85,
                "supporting_facts": [
                    "Client states Miranda was not read until station",
                    "Officer asked about cocaine in patrol car",
                    "Statement 'it's not mine' elicited before Miranda",
                ],
                "source": "CLIENT_NARRATIVE",
                "legal_standard": "Miranda v. Arizona — custodial interrogation",
                "relevant_case_law": [
                    "Miranda v. Arizona",
                    "Rhode Island v. Innis",
                ],
                "suppression_potential": "HIGH",
            },
            {
                "id": "CV003",
                "amendment": "6TH",
                "category": "DENIAL_OF_COUNSEL",
                "description": "Client requested attorney at station but was told "
                "to wait. Questioning continued for 30 minutes.",
                "severity": "CRITICAL",
                "confidence": 0.8,
                "supporting_facts": [
                    "Client requested lawyer at station",
                    "Detective said wait until after paperwork",
                    "30 minutes of questioning before counsel",
                ],
                "source": "CLIENT_NARRATIVE",
                "legal_standard": "Edwards v. Arizona — right to counsel once invoked",
                "relevant_case_law": [
                    "Edwards v. Arizona",
                    "Gideon v. Wainwright",
                ],
                "suppression_potential": "HIGH",
            },
        ],
        "discrepancy_report": [
            {
                "id": "D001",
                "topic": "Consent to search",
                "officer_account": "Defendant verbally consented to search",
                "client_account": "Officer said 'easy way or hard way'; client "
                "felt no choice",
                "significance": "CRITICAL",
                "possible_explanations": [
                    "Officer mischaracterized coerced compliance as consent",
                    "Client may be embellishing",
                ],
                "defense_relevance": "If consent was coerced, all evidence from "
                "the search is suppressible under Bumper v. North Carolina.",
            },
            {
                "id": "D002",
                "topic": "Miranda timing",
                "officer_account": "Miranda read at 2:30 AM at scene",
                "client_account": "Miranda not read until at the station",
                "significance": "CRITICAL",
                "possible_explanations": [
                    "Officer may have read abbreviated rights at scene",
                    "Client may not recall brief reading at scene",
                ],
                "defense_relevance": "If Miranda was not properly administered "
                "before the 'whose cocaine' question, that statement is suppressible.",
            },
            {
                "id": "D003",
                "topic": "Right to counsel",
                "officer_account": "No mention of counsel request",
                "client_account": "Client requested lawyer; was told to wait",
                "significance": "CRITICAL",
                "possible_explanations": [
                    "Officer failed to document counsel request",
                ],
                "defense_relevance": "All statements made after counsel request "
                "must be suppressed under Edwards v. Arizona.",
            },
        ],
        "miranda_updates": {
            "statements_before_miranda": [
                "Client asked 'whose cocaine is that' and responded 'it's not mine'"
            ],
            "waiver_validity": "QUESTIONABLE",
            "suppression_basis": "Client reports Miranda was not read until station. "
            "Incriminating statement elicited before Miranda in patrol car.",
        },
        "search_updates": {
            "consent_given": False,
            "consent_voluntariness": "COERCED",
            "scope_exceeded": None,
            "suppression_basis": "Client reports coercive language ('easy way or hard way'). "
            "Consent was not voluntary under totality of circumstances.",
        },
        "suppression_viability": {
            "score": 78,
            "confidence": 0.75,
            "basis": [
                "Coerced consent to search (4th Amendment)",
                "Pre-Miranda custodial interrogation (5th Amendment)",
                "Denial of right to counsel (6th Amendment)",
            ],
            "risks": [
                "Credibility contest: officer vs. client",
                "Officer may testify consent was voluntary",
                "No recording of interaction",
            ],
            "recommended_motions": [
                "Motion to Suppress Evidence (cocaine from coerced search)",
                "Motion to Suppress Statements (pre-Miranda and post-counsel-request)",
                "Jackson-Denno hearing on voluntariness of statements",
            ],
        },
        "attorney_flags": [
            "CRITICAL: 3 critical violations identified — coerced search, "
            "pre-Miranda interrogation, and denial of counsel.",
            "CRITICAL: Officer Smith has prior sustained complaint for excessive "
            "force and pending consent-procedure complaint.",
            "Request body cam and dash cam footage immediately.",
        ],
    }


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestRightsModels:
    """Test Pydantic model validation for rights scanner types."""

    def test_rights_violation_model(self):
        violation = RightsViolation(
            id="V001",
            amendment="4TH",
            category="WARRANTLESS_SEARCH",
            description="Search conducted without warrant or consent",
            severity="CRITICAL",
            confidence=0.9,
            supporting_facts=["No warrant mentioned", "No consent documented"],
            source="ARREST_REPORT",
            legal_standard="Warrant requirement under Katz v. United States",
            relevant_case_law=["Katz v. United States", "Mapp v. Ohio"],
            suppression_potential="HIGH",
        )
        assert violation.amendment == "4TH"
        assert violation.confidence == 0.9
        assert len(violation.supporting_facts) == 2

    def test_rights_violation_confidence_bounds(self):
        with pytest.raises(Exception):
            RightsViolation(
                id="V001",
                amendment="4TH",
                category="TEST",
                description="test",
                severity="MINOR",
                confidence=1.5,  # Out of bounds
                source="ARREST_REPORT",
            )

    def test_discrepancy_item_model(self):
        item = DiscrepancyItem(
            id="D001",
            topic="Consent to search",
            officer_account="Defendant consented",
            client_account="Officer coerced me",
            significance="CRITICAL",
            possible_explanations=["Officer mischaracterized"],
            defense_relevance="Suppression of evidence",
        )
        assert item.significance == "CRITICAL"

    def test_suppression_viability_model(self):
        sv = SuppressionViability(
            score=85,
            confidence=0.8,
            basis=["Coerced consent", "Miranda violation"],
            risks=["Credibility contest"],
            recommended_motions=["Motion to Suppress"],
        )
        assert sv.score == 85
        assert len(sv.basis) == 2

    def test_suppression_viability_score_bounds(self):
        with pytest.raises(Exception):
            SuppressionViability(score=150, confidence=0.5)

    def test_miranda_analysis_defaults(self):
        ma = MirandaAnalysis()
        assert ma.miranda_given is None
        assert ma.timing == ""
        assert ma.statements_before_miranda == []

    def test_search_analysis_defaults(self):
        sa = SearchAnalysis()
        assert sa.search_occurred is False
        assert sa.warrant_present is None
        assert sa.evidence_found == []

    def test_sixth_amendment_analysis_defaults(self):
        sa = SixthAmendmentAnalysis()
        assert sa.counsel_requested is None
        assert sa.lineup_procedural_issues == []

    def test_eighth_amendment_analysis_defaults(self):
        ea = EighthAmendmentAnalysis()
        assert ea.excessive_bail is None
        assert ea.cruel_conditions == []

    def test_rights_scanner_input_defaults(self):
        inp = RightsScannerInput()
        assert inp.arrest_report == ""
        assert inp.charges == []
        assert inp.pre_interview_flags == []

    def test_rights_scanner_output_full(self):
        output = RightsScannerOutput(
            violations=[
                RightsViolation(
                    id="V001",
                    amendment="5TH",
                    category="MIRANDA_VIOLATION",
                    description="Miranda not read before questioning",
                    severity="CRITICAL",
                    confidence=0.9,
                    source="CLIENT_NARRATIVE",
                )
            ],
            discrepancy_report=[
                DiscrepancyItem(
                    id="D001",
                    topic="Miranda timing",
                    officer_account="Miranda read at scene",
                    client_account="Miranda read at station",
                    significance="CRITICAL",
                )
            ],
            suppression_viability=SuppressionViability(
                score=80,
                confidence=0.75,
                basis=["Pre-Miranda statements"],
                risks=["Credibility"],
                recommended_motions=["Motion to Suppress Statements"],
            ),
            total_violations_found=1,
            critical_violations=1,
            attorney_flags=["CRITICAL: Miranda violation identified"],
        )
        data = output.model_dump()
        assert data["total_violations_found"] == 1
        assert data["critical_violations"] == 1
        assert len(data["violations"]) == 1
        assert data["violations"][0]["amendment"] == "5TH"


# ---------------------------------------------------------------------------
# Agent tests
# ---------------------------------------------------------------------------


class TestRightsScannerAgent:
    """Test the RightsScannerAgent logic (LLM calls mocked)."""

    @pytest.mark.asyncio
    async def test_empty_input_returns_no_violations(self):
        """Agent should handle missing input gracefully."""
        from src.agents.tier2_intake.rights_scanner import RightsScannerAgent

        agent = RightsScannerAgent()
        result = await agent.run({})

        assert result["data"]["total_violations_found"] == 0
        assert result["data"]["violations"] == []
        assert result["confidence"] == "LOW"

    @pytest.mark.asyncio
    async def test_pass1_only_when_no_client_narrative(
        self, sample_arrest_report, sample_officer_conduct, sample_pass1_result
    ):
        """When no client narrative, only Pass 1 runs."""
        from src.agents.tier2_intake.rights_scanner import RightsScannerAgent

        agent = RightsScannerAgent()

        with patch(
            "src.agents.tier2_intake.rights_scanner.call_llm",
            new_callable=AsyncMock,
            return_value=sample_pass1_result,
        ) as mock_llm:
            result = await agent.run(
                {
                    "arrest_report": sample_arrest_report,
                    "officer_conduct": sample_officer_conduct,
                }
            )

            # Only 1 LLM call (pass 1 only, no pass 2)
            assert mock_llm.call_count == 1

        assert result["data"]["total_violations_found"] == 2
        assert result["data"]["discrepancy_report"] == []

    @pytest.mark.asyncio
    async def test_both_passes_with_client_narrative(
        self,
        sample_arrest_report,
        sample_client_narrative,
        sample_officer_conduct,
        sample_pass1_result,
        sample_pass2_result,
    ):
        """When client narrative is provided, both passes run."""
        from src.agents.tier2_intake.rights_scanner import RightsScannerAgent

        agent = RightsScannerAgent()

        with patch(
            "src.agents.tier2_intake.rights_scanner.call_llm",
            new_callable=AsyncMock,
            side_effect=[sample_pass1_result, sample_pass2_result],
        ) as mock_llm:
            result = await agent.run(
                {
                    "arrest_report": sample_arrest_report,
                    "client_narrative": sample_client_narrative,
                    "officer_conduct": sample_officer_conduct,
                }
            )

            # 2 LLM calls (pass 1 + pass 2)
            assert mock_llm.call_count == 2

        data = result["data"]
        # 2 from pass1 + 3 from pass2
        assert data["total_violations_found"] == 5
        assert data["critical_violations"] == 4  # 1 SIGNIFICANT + 3 CRITICAL
        assert len(data["discrepancy_report"]) == 3
        assert data["suppression_viability"]["score"] == 78

    @pytest.mark.asyncio
    async def test_miranda_merge(
        self,
        sample_arrest_report,
        sample_client_narrative,
        sample_pass1_result,
        sample_pass2_result,
    ):
        """Pass 2 Miranda updates merge into Pass 1 analysis."""
        from src.agents.tier2_intake.rights_scanner import RightsScannerAgent

        agent = RightsScannerAgent()

        with patch(
            "src.agents.tier2_intake.rights_scanner.call_llm",
            new_callable=AsyncMock,
            side_effect=[sample_pass1_result, sample_pass2_result],
        ):
            result = await agent.run(
                {
                    "arrest_report": sample_arrest_report,
                    "client_narrative": sample_client_narrative,
                }
            )

        miranda = result["data"]["miranda_analysis"]
        assert miranda["waiver_validity"] == "QUESTIONABLE"
        assert len(miranda["statements_before_miranda"]) > 0

    @pytest.mark.asyncio
    async def test_search_merge(
        self,
        sample_arrest_report,
        sample_client_narrative,
        sample_pass1_result,
        sample_pass2_result,
    ):
        """Pass 2 search updates override Pass 1 when client contradicts."""
        from src.agents.tier2_intake.rights_scanner import RightsScannerAgent

        agent = RightsScannerAgent()

        with patch(
            "src.agents.tier2_intake.rights_scanner.call_llm",
            new_callable=AsyncMock,
            side_effect=[sample_pass1_result, sample_pass2_result],
        ):
            result = await agent.run(
                {
                    "arrest_report": sample_arrest_report,
                    "client_narrative": sample_client_narrative,
                }
            )

        search = result["data"]["search_analysis"]
        # Client says no consent — pass2 override
        assert search["consent_given"] is False
        assert search["consent_voluntariness"] == "COERCED"

    @pytest.mark.asyncio
    async def test_attorney_flags_include_review_required(
        self,
        sample_arrest_report,
        sample_client_narrative,
        sample_pass1_result,
        sample_pass2_result,
    ):
        """Attorney flags must include ATTORNEY REVIEW REQUIRED."""
        from src.agents.tier2_intake.rights_scanner import RightsScannerAgent

        agent = RightsScannerAgent()

        with patch(
            "src.agents.tier2_intake.rights_scanner.call_llm",
            new_callable=AsyncMock,
            side_effect=[sample_pass1_result, sample_pass2_result],
        ):
            result = await agent.run(
                {
                    "arrest_report": sample_arrest_report,
                    "client_narrative": sample_client_narrative,
                }
            )

        flags = result["data"]["attorney_flags"]
        assert any("ATTORNEY REVIEW REQUIRED" in f for f in flags)

    @pytest.mark.asyncio
    async def test_audit_log_records_passes(
        self,
        sample_arrest_report,
        sample_client_narrative,
        sample_pass1_result,
        sample_pass2_result,
    ):
        """Agent audit log records both pass starts and completions."""
        from src.agents.tier2_intake.rights_scanner import RightsScannerAgent

        agent = RightsScannerAgent()

        with patch(
            "src.agents.tier2_intake.rights_scanner.call_llm",
            new_callable=AsyncMock,
            side_effect=[sample_pass1_result, sample_pass2_result],
        ):
            await agent.run(
                {
                    "arrest_report": sample_arrest_report,
                    "client_narrative": sample_client_narrative,
                }
            )

        log_actions = [entry.action for entry in agent.get_audit_log()]
        assert "rights_scan_pass1_started" in log_actions
        assert "rights_scan_pass1_completed" in log_actions
        assert "rights_scan_pass2_started" in log_actions
        assert "rights_scan_pass2_completed" in log_actions
        assert "rights_scan_completed" in log_actions

    @pytest.mark.asyncio
    async def test_confidence_computation(self):
        """Test the confidence computation logic."""
        from src.agents.tier2_intake.rights_scanner import RightsScannerAgent

        agent = RightsScannerAgent()

        # No violations => 0.5 confidence
        assert agent._compute_confidence({"violations": []}) == 0.5

        # Single high-confidence critical violation
        result = agent._compute_confidence(
            {
                "violations": [
                    {"confidence": 0.9, "severity": "CRITICAL"},
                ],
                "discrepancy_report": [],
            }
        )
        assert result == 0.9

        # Critical discrepancies boost confidence
        result_with_disc = agent._compute_confidence(
            {
                "violations": [
                    {"confidence": 0.7, "severity": "MODERATE"},
                ],
                "discrepancy_report": [
                    {"significance": "CRITICAL"},
                    {"significance": "CRITICAL"},
                ],
            }
        )
        assert result_with_disc > 0.7  # Boosted by discrepancies

    @pytest.mark.asyncio
    async def test_wrap_output_structure(self):
        """Verify wrap_output adds required metadata fields."""
        from src.agents.tier2_intake.rights_scanner import RightsScannerAgent

        agent = RightsScannerAgent()
        result = await agent.run({})

        assert "data" in result
        assert "confidence" in result
        assert "source" in result
        assert "timestamp" in result
        assert result["source"] == "rights_scanner"
