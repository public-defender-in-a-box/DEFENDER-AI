"""Tests for the Ethics & Compliance Monitor agent.

Covers all five enforcement pillars:
1. Privilege Protection
2. UPL Boundary
3. Bias Audit
4. Competence Floor
5. Hallucination Detection
"""

from __future__ import annotations

import pytest

from src.agents.cross_cutting.ethics_monitor import EthicsMonitorAgent


@pytest.fixture
def monitor() -> EthicsMonitorAgent:
    return EthicsMonitorAgent()


def _make_input(
    agent_id: str = "test_agent",
    data: dict | str = "",
    confidence: str = "HIGH",
    is_client_facing: bool = False,
    source: str = "test_agent",
    metadata: dict | None = None,
) -> dict:
    output: dict = {
        "data": data,
        "confidence": confidence,
        "source": source,
        "timestamp": "2025-01-01T00:00:00",
    }
    if metadata is not None:
        output["metadata"] = metadata
    return {
        "output": output,
        "agent_id": agent_id,
        "is_client_facing": is_client_facing,
    }


# =========================================================================
# Pillar 1: Privilege Protection
# =========================================================================


class TestPrivilegeProtection:
    @pytest.mark.asyncio
    async def test_pii_ssn_blocked(self, monitor: EthicsMonitorAgent):
        """SSN in output triggers CRITICAL block."""
        result = await monitor.run(
            _make_input(data="Client SSN is 123-45-6789 for records.")
        )
        assert result["blocked"] is True
        flag_cats = [f["category"] for f in result["flags"]]
        assert "PRIVILEGE" in flag_cats
        critical = [f for f in result["flags"] if f["priority"] == "CRITICAL"]
        assert len(critical) >= 1

    @pytest.mark.asyncio
    async def test_pii_email_blocked(self, monitor: EthicsMonitorAgent):
        """Email address in output triggers CRITICAL block."""
        result = await monitor.run(
            _make_input(data="Contact client at john.doe@example.com")
        )
        assert result["blocked"] is True

    @pytest.mark.asyncio
    async def test_pii_phone_blocked(self, monitor: EthicsMonitorAgent):
        """Phone number in output triggers CRITICAL block."""
        result = await monitor.run(
            _make_input(data="Call defendant at 404-555-1234")
        )
        assert result["blocked"] is True

    @pytest.mark.asyncio
    async def test_attorney_work_product_missing_disclaimer(self, monitor: EthicsMonitorAgent):
        """Attorney work-product agent missing ATTORNEY REVIEW REQUIRED."""
        result = await monitor.run(
            _make_input(
                agent_id="motion_drafter",
                data="Here is the motion to suppress evidence.",
            )
        )
        priv_flags = [f for f in result["flags"] if f["category"] == "PRIVILEGE"]
        assert len(priv_flags) >= 1
        assert any("ATTORNEY REVIEW REQUIRED" in f["description"] for f in priv_flags)

    @pytest.mark.asyncio
    async def test_attorney_work_product_with_disclaimer_passes(self, monitor: EthicsMonitorAgent):
        """Work-product with proper disclaimer passes privilege check."""
        result = await monitor.run(
            _make_input(
                agent_id="motion_drafter",
                data="DRAFT — ATTORNEY REVIEW REQUIRED\nMotion to suppress.",
            )
        )
        priv_flags = [
            f for f in result["flags"]
            if f["category"] == "PRIVILEGE" and f["priority"] in ("CRITICAL", "HIGH")
        ]
        assert len(priv_flags) == 0

    @pytest.mark.asyncio
    async def test_draft_without_review_disclaimer(self, monitor: EthicsMonitorAgent):
        """DRAFT in output without ATTORNEY REVIEW REQUIRED flagged."""
        result = await monitor.run(
            _make_input(data="DRAFT motion for bond reduction.")
        )
        priv_flags = [f for f in result["flags"] if f["category"] == "PRIVILEGE"]
        assert len(priv_flags) >= 1

    @pytest.mark.asyncio
    async def test_clean_output_no_privilege_flags(self, monitor: EthicsMonitorAgent):
        """Clean output with no PII or drafts passes without privilege flags."""
        result = await monitor.run(
            _make_input(data="The statute of limitations is 4 years.")
        )
        priv_flags = [f for f in result["flags"] if f["category"] == "PRIVILEGE"]
        assert len(priv_flags) == 0


# =========================================================================
# Pillar 2: UPL Boundary
# =========================================================================


class TestUPLBoundary:
    @pytest.mark.asyncio
    async def test_advisory_phrase_in_client_facing_blocked(self, monitor: EthicsMonitorAgent):
        """Client-facing output with advisory language is CRITICAL blocked."""
        result = await monitor.run(
            _make_input(
                agent_id="intake_conductor",
                data="Based on the evidence, you should plead guilty.",
                is_client_facing=True,
            )
        )
        assert result["blocked"] is True
        upl_flags = [f for f in result["flags"] if f["category"] == "UPL"]
        assert any(f["priority"] == "CRITICAL" for f in upl_flags)

    @pytest.mark.asyncio
    async def test_multiple_upl_phrases(self, monitor: EthicsMonitorAgent):
        """Multiple UPL phrases each generate their own flag."""
        result = await monitor.run(
            _make_input(
                data="I advise you to take the deal. You must plead guilty.",
                is_client_facing=True,
            )
        )
        upl_critical = [
            f for f in result["flags"]
            if f["category"] == "UPL" and f["priority"] == "CRITICAL"
        ]
        assert len(upl_critical) >= 2

    @pytest.mark.asyncio
    async def test_non_client_facing_no_upl_block(self, monitor: EthicsMonitorAgent):
        """Advisory language in internal output does NOT trigger UPL block."""
        result = await monitor.run(
            _make_input(
                agent_id="case_prep",
                data="Attorney should recommend client consider plea options.",
                is_client_facing=False,
            )
        )
        upl_critical = [
            f for f in result["flags"]
            if f["category"] == "UPL" and f["priority"] == "CRITICAL"
        ]
        assert len(upl_critical) == 0

    @pytest.mark.asyncio
    async def test_client_facing_missing_disclaimer(self, monitor: EthicsMonitorAgent):
        """Client-facing output without not-legal-advice disclaimer flagged."""
        result = await monitor.run(
            _make_input(
                data="Here are the charges against you and possible penalties.",
                is_client_facing=True,
            )
        )
        upl_flags = [f for f in result["flags"] if f["category"] == "UPL"]
        assert any("not legal advice" in f["description"].lower() or "disclaimer" in f["description"].lower() for f in upl_flags)

    @pytest.mark.asyncio
    async def test_client_facing_with_disclaimer_passes(self, monitor: EthicsMonitorAgent):
        """Client-facing output with proper disclaimer passes."""
        result = await monitor.run(
            _make_input(
                data=(
                    "Here are the charges. "
                    "This information is not legal advice. "
                    "Please consult your attorney before making any decisions."
                ),
                is_client_facing=True,
            )
        )
        upl_disclaimer_flags = [
            f for f in result["flags"]
            if f["category"] == "UPL" and "disclaimer" in f["description"].lower()
        ]
        assert len(upl_disclaimer_flags) == 0

    @pytest.mark.asyncio
    async def test_plea_trial_missing_decision_support(self, monitor: EthicsMonitorAgent):
        """Plea/trial output without DECISION SUPPORT ONLY disclaimer flagged."""
        result = await monitor.run(
            _make_input(
                agent_id="plea_trial_analyst",
                data={"recommendation": "Defendant should consider plea agreement."},
            )
        )
        upl_flags = [f for f in result["flags"] if f["category"] == "UPL"]
        assert any("DECISION SUPPORT ONLY" in f["description"] for f in upl_flags)

    @pytest.mark.asyncio
    async def test_motion_drafter_missing_draft_marker(self, monitor: EthicsMonitorAgent):
        """Motion drafter output not marked DRAFT flagged."""
        result = await monitor.run(
            _make_input(
                agent_id="motion_drafter",
                data="Motion to Suppress Evidence pursuant to O.C.G.A. § 17-5-30",
            )
        )
        upl_flags = [f for f in result["flags"] if f["category"] == "UPL"]
        assert any("DRAFT" in f["description"] for f in upl_flags)


# =========================================================================
# Pillar 3: Bias Audit
# =========================================================================


class TestBiasAudit:
    @pytest.mark.asyncio
    async def test_demographic_term_near_outcome_flagged(self, monitor: EthicsMonitorAgent):
        """Demographic term correlated with outcome language triggers HIGH flag."""
        result = await monitor.run(
            _make_input(
                agent_id="sentencing_agent",
                data=(
                    "The african american defendant faces a sentence of 5-10 years. "
                    "Recommendation: standard sentencing guidelines apply."
                ),
            )
        )
        bias_flags = [f for f in result["flags"] if f["category"] == "BIAS"]
        assert len(bias_flags) >= 1

    @pytest.mark.asyncio
    async def test_stereotyping_phrase_blocked(self, monitor: EthicsMonitorAgent):
        """Stereotyping phrases in sentencing output trigger CRITICAL block."""
        result = await monitor.run(
            _make_input(
                agent_id="sentencing_agent",
                data="Defendants of this background typically receive longer sentences.",
            )
        )
        assert result["blocked"] is True
        bias_flags = [f for f in result["flags"] if f["category"] == "BIAS"]
        assert any(f["priority"] == "CRITICAL" for f in bias_flags)

    @pytest.mark.asyncio
    async def test_non_auditable_agent_skipped(self, monitor: EthicsMonitorAgent):
        """Agents not in BIAS_AUDITABLE_AGENTS skip bias audit."""
        result = await monitor.run(
            _make_input(
                agent_id="charge_processing",
                data="The african american defendant was charged under O.C.G.A. § 16-13-30.",
            )
        )
        bias_flags = [f for f in result["flags"] if f["category"] == "BIAS"]
        assert len(bias_flags) == 0

    @pytest.mark.asyncio
    async def test_multiple_demographic_terms_medium_flag(self, monitor: EthicsMonitorAgent):
        """Multiple demographic terms without outcome correlation → MEDIUM."""
        result = await monitor.run(
            _make_input(
                agent_id="case_law_agent",
                data=(
                    "Review of cases involving hispanic, low income, "
                    "and elderly defendants in similar jurisdictions."
                ),
            )
        )
        bias_flags = [f for f in result["flags"] if f["category"] == "BIAS"]
        assert len(bias_flags) >= 1

    @pytest.mark.asyncio
    async def test_clean_output_no_bias_flags(self, monitor: EthicsMonitorAgent):
        """Output without demographic terms passes bias audit cleanly."""
        result = await monitor.run(
            _make_input(
                agent_id="sentencing_agent",
                data="Standard sentencing range is 1-5 years under O.C.G.A. § 16-13-30.",
            )
        )
        bias_flags = [f for f in result["flags"] if f["category"] == "BIAS"]
        assert len(bias_flags) == 0

    @pytest.mark.asyncio
    async def test_plea_analyst_stereotyping_blocked(self, monitor: EthicsMonitorAgent):
        """Plea analyst with stereotyping phrase triggers CRITICAL."""
        result = await monitor.run(
            _make_input(
                agent_id="plea_trial_analyst",
                data={
                    "recommendation": (
                        "DECISION SUPPORT ONLY: statistically more likely "
                        "to reoffend based on demographics."
                    )
                },
            )
        )
        bias_flags = [f for f in result["flags"] if f["category"] == "BIAS"]
        assert any(f["priority"] == "CRITICAL" for f in bias_flags)


# =========================================================================
# Pillar 4: Competence Floor
# =========================================================================


class TestCompetenceFloor:
    @pytest.mark.asyncio
    async def test_low_confidence_flagged(self, monitor: EthicsMonitorAgent):
        """LOW confidence output triggers MEDIUM competence flag."""
        result = await monitor.run(
            _make_input(confidence="LOW")
        )
        comp_flags = [f for f in result["flags"] if f["category"] == "COMPETENCE"]
        assert len(comp_flags) >= 1
        assert any("LOW confidence" in f["description"] for f in comp_flags)

    @pytest.mark.asyncio
    async def test_unrated_confidence_flagged(self, monitor: EthicsMonitorAgent):
        """UNRATED confidence triggers HIGH competence flag."""
        result = await monitor.run(
            _make_input(confidence="UNRATED")
        )
        comp_flags = [f for f in result["flags"] if f["category"] == "COMPETENCE"]
        assert any("UNRATED" in f["description"] for f in comp_flags)

    @pytest.mark.asyncio
    async def test_null_data_blocked(self, monitor: EthicsMonitorAgent):
        """Null data triggers CRITICAL competence block."""
        result = await monitor.run(
            _make_input(data=None)
        )
        assert result["blocked"] is True
        comp_flags = [f for f in result["flags"] if f["category"] == "COMPETENCE"]
        assert any(f["priority"] == "CRITICAL" for f in comp_flags)

    @pytest.mark.asyncio
    async def test_empty_data_flagged(self, monitor: EthicsMonitorAgent):
        """Empty dict data triggers HIGH competence flag."""
        result = await monitor.run(
            _make_input(data={})
        )
        comp_flags = [f for f in result["flags"] if f["category"] == "COMPETENCE"]
        assert any("empty" in f["description"].lower() for f in comp_flags)

    @pytest.mark.asyncio
    async def test_missing_source_flagged(self, monitor: EthicsMonitorAgent):
        """Output missing source attribution triggers MEDIUM flag."""
        inp = _make_input(data="Some valid data")
        inp["output"]["source"] = ""
        result = await monitor.run(inp)
        comp_flags = [f for f in result["flags"] if f["category"] == "COMPETENCE"]
        assert any("source" in f["description"].lower() for f in comp_flags)

    @pytest.mark.asyncio
    async def test_high_confidence_passes(self, monitor: EthicsMonitorAgent):
        """HIGH confidence output passes competence check cleanly."""
        result = await monitor.run(
            _make_input(confidence="HIGH", data="Valid analysis output.")
        )
        comp_flags = [f for f in result["flags"] if f["category"] == "COMPETENCE"]
        assert len(comp_flags) == 0

    @pytest.mark.asyncio
    async def test_medium_confidence_passes(self, monitor: EthicsMonitorAgent):
        """MEDIUM confidence passes without competence flags."""
        result = await monitor.run(
            _make_input(confidence="MEDIUM", data="Partial analysis output.")
        )
        comp_flags = [f for f in result["flags"] if f["category"] == "COMPETENCE"]
        assert len(comp_flags) == 0


# =========================================================================
# Pillar 5: Hallucination Detection
# =========================================================================


class TestHallucinationDetection:
    @pytest.mark.asyncio
    async def test_invalid_statute_title_blocked(self, monitor: EthicsMonitorAgent):
        """Invalid Georgia statute title number triggers CRITICAL block."""
        result = await monitor.run(
            _make_input(
                agent_id="statute_agent",
                data="Under O.C.G.A. § 99-1-1, the defendant is charged.",
            )
        )
        assert result["blocked"] is True
        hal_flags = [f for f in result["flags"] if f["category"] == "HALLUCINATION"]
        assert any(f["priority"] == "CRITICAL" for f in hal_flags)
        assert any("Title 99" in f["description"] for f in hal_flags)

    @pytest.mark.asyncio
    async def test_valid_statute_passes(self, monitor: EthicsMonitorAgent):
        """Valid Georgia statute reference passes hallucination check."""
        result = await monitor.run(
            _make_input(
                agent_id="statute_agent",
                data="Under O.C.G.A. § 16-13-30, possession is a felony.",
            )
        )
        hal_flags = [
            f for f in result["flags"]
            if f["category"] == "HALLUCINATION" and "statute" in f["description"].lower()
        ]
        assert len(hal_flags) == 0

    @pytest.mark.asyncio
    async def test_future_dated_citation_blocked(self, monitor: EthicsMonitorAgent):
        """Citation with future year triggers CRITICAL block."""
        result = await monitor.run(
            _make_input(
                agent_id="case_law_agent",
                data="In Smith v. Georgia, 300 Ga. App. 123 (2099), the court held...",
            )
        )
        assert result["blocked"] is True
        hal_flags = [f for f in result["flags"] if f["category"] == "HALLUCINATION"]
        assert any("2099" in f["description"] for f in hal_flags)

    @pytest.mark.asyncio
    async def test_fabrication_signal_phrase_flagged(self, monitor: EthicsMonitorAgent):
        """Fabrication signal phrase triggers HIGH flag."""
        result = await monitor.run(
            _make_input(
                data="As established in the landmark case of Jones v. State, the rule is clear.",
            )
        )
        hal_flags = [f for f in result["flags"] if f["category"] == "HALLUCINATION"]
        assert len(hal_flags) >= 1
        assert any(f["priority"] == "HIGH" for f in hal_flags)

    @pytest.mark.asyncio
    async def test_majority_unverified_citations_flagged(self, monitor: EthicsMonitorAgent):
        """More than 50% unverified citations triggers HIGH flag."""
        result = await monitor.run(
            _make_input(
                agent_id="case_law_agent",
                data={
                    "analysis": "Case law review complete.",
                    "citations": [
                        {"citation": "Smith v. State", "verification_status": "UNVERIFIED"},
                        {"citation": "Jones v. State", "verification_status": "UNVERIFIED"},
                        {"citation": "Brown v. State", "verification_status": "VERIFIED"},
                    ],
                },
            )
        )
        hal_flags = [f for f in result["flags"] if f["category"] == "HALLUCINATION"]
        assert any("UNVERIFIED" in f["description"] for f in hal_flags)

    @pytest.mark.asyncio
    async def test_confidence_mismatch_flagged(self, monitor: EthicsMonitorAgent):
        """HIGH confidence with many hedge words triggers MEDIUM flag."""
        result = await monitor.run(
            _make_input(
                confidence="HIGH",
                data=(
                    "The defendant possibly committed the crime. Perhaps the evidence "
                    "might show guilt. It is uncertain whether the witness was credible. "
                    "It appears that seemingly the facts may be interpreted this way."
                ),
            )
        )
        hal_flags = [f for f in result["flags"] if f["category"] == "HALLUCINATION"]
        assert any("hedging" in f["description"].lower() or "confidence" in f["description"].lower() for f in hal_flags)

    @pytest.mark.asyncio
    async def test_clean_output_no_hallucination_flags(self, monitor: EthicsMonitorAgent):
        """Clean output with valid references passes hallucination check."""
        result = await monitor.run(
            _make_input(
                agent_id="statute_agent",
                data="Under O.C.G.A. § 16-13-30(a), possession of cocaine is a felony.",
            )
        )
        hal_flags = [f for f in result["flags"] if f["category"] == "HALLUCINATION"]
        assert len(hal_flags) == 0

    @pytest.mark.asyncio
    async def test_non_citation_agent_skips_citation_checks(self, monitor: EthicsMonitorAgent):
        """Non-citation-producing agent skips citation-specific checks."""
        result = await monitor.run(
            _make_input(
                agent_id="fact_gatherer",
                data={
                    "facts": "The defendant was arrested on January 15.",
                    "citations": [
                        {"citation": "Fake v. Case", "verification_status": "UNVERIFIED"},
                        {"citation": "Made v. Up", "verification_status": "UNVERIFIED"},
                    ],
                },
            )
        )
        # fact_gatherer is not in CITATION_PRODUCING_AGENTS
        hal_citation_flags = [
            f for f in result["flags"]
            if f["category"] == "HALLUCINATION" and "UNVERIFIED" in f["description"]
        ]
        assert len(hal_citation_flags) == 0


# =========================================================================
# Cross-pillar integration tests
# =========================================================================


class TestCrossPillarIntegration:
    @pytest.mark.asyncio
    async def test_multiple_violations_all_flagged(self, monitor: EthicsMonitorAgent):
        """Output with violations across multiple pillars gets all flags."""
        result = await monitor.run(
            _make_input(
                agent_id="sentencing_agent",
                data=(
                    "The african american defendant's SSN 123-45-6789 is on file. "
                    "Defendants of this background typically receive harsh sentences. "
                    "As established in the landmark case of Fake v. State, "
                    "O.C.G.A. § 99-1-1 applies."
                ),
                confidence="LOW",
            )
        )
        assert result["blocked"] is True
        categories = {f["category"] for f in result["flags"]}
        assert "PRIVILEGE" in categories   # SSN leak
        assert "BIAS" in categories        # stereotyping
        assert "HALLUCINATION" in categories  # invalid statute
        assert "COMPETENCE" in categories  # LOW confidence

    @pytest.mark.asyncio
    async def test_clean_high_confidence_output_passes(self, monitor: EthicsMonitorAgent):
        """Clean, high-confidence, properly formatted output has no flags."""
        result = await monitor.run(
            _make_input(
                agent_id="statute_agent",
                data="Analysis of O.C.G.A. § 16-13-30(a) complete.",
                confidence="HIGH",
                is_client_facing=False,
            )
        )
        assert result["blocked"] is False
        assert len(result["flags"]) == 0

    @pytest.mark.asyncio
    async def test_audit_trail_populated(self, monitor: EthicsMonitorAgent):
        """Every ethics check produces audit entries."""
        result = await monitor.run(
            _make_input(data="Simple test output.")
        )
        assert len(result["audit_entries"]) >= 1

    @pytest.mark.asyncio
    async def test_review_result_has_all_pillar_details(self, monitor: EthicsMonitorAgent):
        """EthicsReviewResult includes detail objects for all pillars."""
        result = await monitor.run(
            _make_input(
                agent_id="case_law_agent",
                data="Valid case analysis.",
            )
        )
        assert result["privilege_check"] is not None
        assert result["upl_check"] is not None
        assert result["bias_audit"] is not None
        assert result["competence_check"] is not None
        assert result["hallucination_check"] is not None
