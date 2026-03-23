"""Tests for Tier 2 Intake Specialist agents and their Pydantic models.

Tests cover:
1. Pydantic model validation and serialization for all output models
2. Agent golden-output tests using mocked LLM responses
3. Edge cases: empty inputs, malformed LLM responses, confidence scoring
4. Graph integration: intake_sub_agents_node wiring
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.agents.tier2_intake.collateral_agent import CollateralConsequencesAgent
from src.agents.tier2_intake.fact_gatherer import FactGathererAgent
from src.agents.tier2_intake.personal_circumstances import PersonalCircumstancesAgent
from src.models.intake import (
    BailProfile,
    CollateralConsequence,
    CollateralConsequencesOutput,
    CommunityTie,
    DiversionEligibility,
    ElementCoverage,
    EvidenceItem,
    FactGatheringOutput,
    FlightRiskFactor,
    MitigationNarrative,
    PadillaAssessment,
    PersonalCircumstancesOutput,
    TargetedQuestion,
    TimelineEvent,
    TreatmentNeed,
    WitnessRecord,
)


# ---------------------------------------------------------------------------
# Pydantic model tests
# ---------------------------------------------------------------------------


class TestFactGatheringModels:
    """Test Pydantic models for the Fact Gathering Agent."""

    def test_timeline_event_creation(self):
        evt = TimelineEvent(
            id="evt_001",
            timestamp_description="approximately 2:30 AM on January 15, 2024",
            event="Client was stopped by Officer Smith on Peachtree St",
            source="CLIENT_STATEMENT",
            confidence="HIGH",
            related_charge_ids=["charge_001"],
        )
        assert evt.source == "CLIENT_STATEMENT"
        assert evt.confidence == "HIGH"
        assert len(evt.related_charge_ids) == 1

    def test_witness_record_creation(self):
        wit = WitnessRecord(
            id="wit_001",
            name="Maria Garcia",
            relationship="EYEWITNESS",
            observed_events=["Observed defendant near intersection"],
            favorable=False,
        )
        assert wit.favorable is False
        assert wit.relationship == "EYEWITNESS"

    def test_evidence_item_creation(self):
        evi = EvidenceItem(
            id="evi_001",
            description="Body camera footage from Officer Smith",
            evidence_type="DIGITAL",
            location="APD Zone 3 evidence room",
            preservation_status="AT_RISK",
            relevance="CRITICAL",
            chain_of_custody_concern=False,
            notes="Body cam footage typically retained 90 days — preservation letter needed",
        )
        assert evi.preservation_status == "AT_RISK"
        assert evi.relevance == "CRITICAL"

    def test_element_coverage_creation(self):
        ec = ElementCoverage(
            charge_id="charge_001",
            element="knowingly possessed",
            covered=True,
            client_position="DENIES",
            confidence="MEDIUM",
            gaps=["Need to clarify proximity to discarded bag"],
        )
        assert ec.client_position == "DENIES"
        assert len(ec.gaps) == 1

    def test_fact_gathering_output_serialization(self):
        output = FactGatheringOutput(
            timeline=[
                TimelineEvent(
                    id="evt_001",
                    timestamp_description="2:30 AM",
                    event="Traffic stop",
                    source="CLIENT_STATEMENT",
                    confidence="HIGH",
                )
            ],
            witnesses=[],
            evidence_inventory=[],
            scene_description="Intersection of Peachtree and Andrew Young Blvd",
            element_coverage=[],
            follow_up_questions=[],
            credibility_notes=["Client account is consistent with timeline"],
        )
        data = output.model_dump()
        assert len(data["timeline"]) == 1
        assert data["scene_description"] != ""


class TestCollateralConsequencesModels:
    """Test Pydantic models for the Collateral Consequences Agent."""

    def test_collateral_consequence_creation(self):
        cc = CollateralConsequence(
            id="cc_001",
            category="IMMIGRATION",
            description="Cocaine possession is a controlled substance offense triggering deportation",
            severity="SEVERE",
            charge_specific=True,
            related_charge_ids=["charge_001"],
            affects_plea_strategy=True,
            federal_statute="8 U.S.C. § 1227(a)(2)(B)(i)",
            mitigation_possible=True,
            mitigation_strategy="Negotiate to non-deportable offense if possible",
        )
        assert cc.severity == "SEVERE"
        assert cc.affects_plea_strategy is True

    def test_padilla_assessment_creation(self):
        padilla = PadillaAssessment(
            non_citizen=True,
            immigration_status="LPR",
            deportation_risk="CERTAIN",
            aggravated_felony_risk=False,
            crime_involving_moral_turpitude=True,
            controlled_substance_offense=True,
            advisory_required=True,
            advisory_summary="Client is an LPR. Cocaine possession is a deportable offense.",
        )
        assert padilla.advisory_required is True
        assert padilla.deportation_risk == "CERTAIN"

    def test_collateral_output_serialization(self):
        output = CollateralConsequencesOutput(
            consequences=[],
            padilla_assessment=PadillaAssessment(
                non_citizen=False,
                advisory_required=False,
            ),
            plea_strategy_impact="No significant collateral consequences identified.",
        )
        data = output.model_dump()
        assert data["padilla_assessment"]["non_citizen"] is False


class TestPersonalCircumstancesModels:
    """Test Pydantic models for the Personal Circumstances Agent."""

    def test_community_tie_creation(self):
        tie = CommunityTie(
            category="EMPLOYMENT",
            description="Employed as line cook at Waffle House for 3 years",
            strength="STRONG",
            verifiable=True,
            verification_source="Employer pay stubs",
        )
        assert tie.strength == "STRONG"
        assert tie.verifiable is True

    def test_flight_risk_factor_creation(self):
        frf = FlightRiskFactor(
            factor="No prior failures to appear",
            direction="DECREASES_RISK",
            weight="HIGH",
        )
        assert frf.direction == "DECREASES_RISK"

    def test_bail_profile_creation(self):
        profile = BailProfile(
            community_ties=[],
            flight_risk_factors=[],
            recommendation="LOW_BOND",
            recommended_conditions=["Drug testing", "Curfew"],
        )
        assert profile.recommendation == "LOW_BOND"
        assert len(profile.recommended_conditions) == 2

    def test_diversion_eligibility_creation(self):
        div = DiversionEligibility(
            program="FIRST_OFFENDER",
            eligible=True,
            basis="No prior felony convictions, charge not excluded",
            georgia_authority="O.C.G.A. § 42-8-60",
        )
        assert div.eligible is True
        assert "42-8-60" in div.georgia_authority

    def test_treatment_need_creation(self):
        need = TreatmentNeed(
            category="SUBSTANCE_ABUSE",
            description="Client reports occasional cocaine use",
            urgency="NEAR_TERM",
            relevant_to_diversion=True,
            relevant_to_mitigation=True,
        )
        assert need.relevant_to_diversion is True

    def test_personal_circumstances_output_serialization(self):
        output = PersonalCircumstancesOutput(
            bail_profile=BailProfile(),
            mitigation_narrative=MitigationNarrative(summary="Draft narrative."),
            first_offender_eligible=True,
            first_offender_notes="Eligible under O.C.G.A. § 42-8-60",
        )
        data = output.model_dump()
        assert data["first_offender_eligible"] is True


# ---------------------------------------------------------------------------
# Golden-output agent tests (mocked LLM)
# ---------------------------------------------------------------------------

# Realistic LLM response for the Fact Gatherer
_FACT_GATHERER_GOLDEN_RESPONSE = {
    "timeline": [
        {
            "id": "evt_001",
            "timestamp_description": "approximately 2:30 AM on January 15, 2024",
            "event": "Client was walking near Peachtree St and Andrew Young Blvd",
            "source": "CLIENT_STATEMENT",
            "confidence": "HIGH",
            "related_charge_ids": ["charge_001"],
        },
        {
            "id": "evt_002",
            "timestamp_description": "approximately 2:35 AM on January 15, 2024",
            "event": "Officer Smith approached client and conducted stop",
            "source": "CLIENT_STATEMENT",
            "confidence": "HIGH",
            "related_charge_ids": ["charge_001"],
        },
        {
            "id": "evt_003",
            "timestamp_description": "shortly after stop",
            "event": "Client states he did not discard any bag; bag was already on ground",
            "source": "CLIENT_STATEMENT",
            "confidence": "MEDIUM",
            "related_charge_ids": ["charge_001"],
        },
    ],
    "witnesses": [
        {
            "id": "wit_001",
            "name": "James Smith",
            "relationship": "OTHER",
            "observed_events": ["Claimed to see defendant discard bag"],
            "favorable": False,
            "notes": "Arresting officer — Badge #4521",
        },
        {
            "id": "wit_002",
            "name": "",
            "relationship": "ALIBI",
            "observed_events": ["Client says friend was with him at time of stop"],
            "favorable": True,
            "notes": "Client cannot remember full name, says 'Marcus'",
        },
    ],
    "evidence_inventory": [
        {
            "id": "evi_001",
            "description": "Plastic bag with white powder (alleged cocaine, 2.3g)",
            "evidence_type": "PHYSICAL",
            "location": "APD evidence room",
            "preservation_status": "PRESERVED",
            "relevance": "CRITICAL",
            "chain_of_custody_concern": True,
            "notes": "Client denies bag was his — chain of custody from ground to lab is key",
        },
        {
            "id": "evi_002",
            "description": "Body camera footage from Officer Smith",
            "evidence_type": "DIGITAL",
            "location": "APD Zone 3",
            "preservation_status": "AT_RISK",
            "relevance": "CRITICAL",
            "chain_of_custody_concern": False,
            "notes": "Preservation letter needed — APD retains for 90 days",
        },
    ],
    "scene_description": (
        "The intersection of Peachtree St and Andrew Young International Blvd "
        "in downtown Atlanta. Well-lit area with surveillance cameras on nearby "
        "buildings. Client says he was walking from a bar. Officer approached "
        "from a patrol car."
    ),
    "element_coverage": [
        {
            "charge_id": "charge_001",
            "element": "knowingly possessed",
            "covered": True,
            "client_position": "DENIES",
            "confidence": "MEDIUM",
            "gaps": ["Need to establish whether bag was within client's reach/control"],
        },
        {
            "charge_id": "charge_001",
            "element": "controlled substance (cocaine)",
            "covered": False,
            "client_position": "NO_RESPONSE",
            "confidence": "LOW",
            "gaps": ["Lab results not yet available to verify substance identity"],
        },
    ],
    "follow_up_questions": [
        {
            "question": "Can you describe exactly where the bag was when the officer pointed it out?",
            "relevant_charge_id": "charge_001",
            "relevant_element": "knowingly possessed",
            "priority": "MUST_ASK",
        },
        {
            "question": "Do you know if there are surveillance cameras at that intersection?",
            "relevant_charge_id": "charge_001",
            "relevant_element": "knowingly possessed",
            "priority": "SHOULD_ASK",
        },
    ],
    "credibility_notes": [
        "Client's account is internally consistent regarding his location and timing.",
        "Client's denial of discarding the bag contradicts the officer's report — "
        "body camera footage will be dispositive.",
    ],
}

_COLLATERAL_GOLDEN_RESPONSE = {
    "consequences": [
        {
            "id": "cc_001",
            "category": "EMPLOYMENT",
            "description": "Drug conviction will appear on background checks, limiting employment opportunities",
            "severity": "MODERATE",
            "charge_specific": True,
            "related_charge_ids": ["charge_001"],
            "affects_plea_strategy": True,
            "georgia_statute": "",
            "federal_statute": "",
            "mitigation_possible": True,
            "mitigation_strategy": "First Offender Act would avoid conviction record",
        },
        {
            "id": "cc_002",
            "category": "CIVIL_RIGHTS",
            "description": "Felony conviction would result in loss of firearm rights under Georgia law",
            "severity": "MODERATE",
            "charge_specific": True,
            "related_charge_ids": ["charge_001"],
            "affects_plea_strategy": False,
            "georgia_statute": "O.C.G.A. § 16-11-131",
            "federal_statute": "18 U.S.C. § 922(g)(1)",
            "mitigation_possible": True,
            "mitigation_strategy": "If charged as misdemeanor, firearm rights preserved",
        },
        {
            "id": "cc_003",
            "category": "EDUCATION",
            "description": "Drug conviction may affect federal financial aid eligibility",
            "severity": "MINOR",
            "charge_specific": True,
            "related_charge_ids": ["charge_001"],
            "affects_plea_strategy": False,
            "georgia_statute": "",
            "federal_statute": "21 U.S.C. § 862",
            "mitigation_possible": True,
            "mitigation_strategy": "First Offender Act avoids conviction for financial aid purposes",
        },
    ],
    "padilla_assessment": {
        "non_citizen": False,
        "immigration_status": "CITIZEN",
        "deportation_risk": "UNLIKELY",
        "aggravated_felony_risk": False,
        "crime_involving_moral_turpitude": False,
        "controlled_substance_offense": True,
        "firearm_offense": False,
        "domestic_violence_offense": False,
        "advisory_required": False,
        "advisory_summary": "Client is a US citizen. No immigration consequences.",
    },
    "plea_strategy_impact": (
        "The primary collateral consequence concern is the employment impact of a "
        "drug conviction on background checks. The Georgia First Offender Act "
        "(O.C.G.A. § 42-8-60) should be explored as it would avoid a formal "
        "conviction, preserving the client's employment prospects."
    ),
    "priority_consequences": ["cc_001"],
    "client_stated_priorities": ["keeping my job", "avoiding jail"],
}

_PERSONAL_GOLDEN_RESPONSE = {
    "bail_profile": {
        "community_ties": [
            {
                "category": "EMPLOYMENT",
                "description": "Employed as line cook at Waffle House for 3 years",
                "strength": "STRONG",
                "verifiable": True,
                "verification_source": "Pay stubs, employer contact",
            },
            {
                "category": "RESIDENCE",
                "description": "Rents apartment in East Atlanta for 2 years",
                "strength": "MODERATE",
                "verifiable": True,
                "verification_source": "Lease agreement",
            },
            {
                "category": "FAMILY",
                "description": "Mother and sister live in Atlanta area",
                "strength": "MODERATE",
                "verifiable": True,
                "verification_source": "Family contact information",
            },
        ],
        "flight_risk_factors": [
            {
                "factor": "No prior failures to appear",
                "direction": "DECREASES_RISK",
                "weight": "HIGH",
                "notes": "",
            },
            {
                "factor": "Stable employment and residence",
                "direction": "DECREASES_RISK",
                "weight": "HIGH",
                "notes": "",
            },
        ],
        "danger_to_community_factors": ["No violent history", "Charge is possession, not distribution"],
        "recommendation": "OR",
        "recommended_conditions": ["Drug testing", "Check-in with pretrial services"],
        "georgia_bail_schedule_note": "Fulton County bail schedule: possession < 1 oz cocaine — standard bond",
    },
    "mitigation_narrative": {
        "summary": (
            "DRAFT — ATTORNEY REVIEW REQUIRED. John Doe is a 28-year-old Atlanta "
            "resident with strong community ties. He has maintained steady employment "
            "as a line cook for three years and has no prior criminal record. He lives "
            "independently and maintains close family relationships. These factors "
            "demonstrate stability and suggest this incident is not reflective of "
            "his character."
        ),
        "key_themes": ["employment stability", "community ties", "no prior record"],
        "favorable_factors": [
            "3 years continuous employment",
            "Stable housing",
            "Family support in area",
            "No prior criminal history",
        ],
        "areas_needing_development": [
            "Substance abuse assessment if applicable",
            "Character reference letters",
        ],
        "recommended_documentation": [
            "Employment verification letter from Waffle House",
            "Lease agreement",
            "Character reference letters from family and employer",
        ],
    },
    "diversion_eligibility": [
        {
            "program": "FIRST_OFFENDER",
            "eligible": True,
            "basis": "No prior felony convictions, possession charge not excluded from First Offender",
            "georgia_authority": "O.C.G.A. § 42-8-60",
            "conditions": ["Probation", "Drug testing", "Community service"],
            "notes": "Strongest option — avoids conviction record entirely",
        },
        {
            "program": "PRETRIAL_DIVERSION",
            "eligible": True,
            "basis": "First-time offender, non-violent charge, DA discretion",
            "georgia_authority": "O.C.G.A. § 42-8-34",
            "conditions": ["Drug treatment program", "Community service", "Regular check-ins"],
            "notes": "Must apply to DA's office; acceptance not guaranteed",
        },
        {
            "program": "DRUG_COURT",
            "eligible": True,
            "basis": "Drug-related offense, substance use may be a factor",
            "georgia_authority": "O.C.G.A. § 15-1-15",
            "conditions": ["Intensive drug treatment", "Regular court appearances", "Drug testing"],
            "notes": "Fulton County has an active Drug Court program",
        },
    ],
    "treatment_needs": [
        {
            "category": "SUBSTANCE_ABUSE",
            "description": "Assessment recommended to determine extent of substance use",
            "urgency": "NEAR_TERM",
            "relevant_to_diversion": True,
            "relevant_to_mitigation": True,
        },
    ],
    "first_offender_eligible": True,
    "first_offender_notes": (
        "Client has no prior felony convictions. Cocaine possession under "
        "O.C.G.A. § 16-13-30(a) is not excluded from First Offender Act "
        "eligibility. This is the strongest pathway to avoid a conviction record."
    ),
    "youthful_offender_eligible": False,
    "veterans_status": False,
}


class TestFactGathererAgent:
    """Golden-output tests for the Fact Gathering Agent."""

    @pytest.mark.asyncio
    async def test_fact_gatherer_golden_output(self):
        """Test fact gathering with realistic Georgia cocaine possession case."""
        agent = FactGathererAgent()

        with patch("src.agents.tier2_intake.fact_gatherer.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _FACT_GATHERER_GOLDEN_RESPONSE

            result = await agent.run({
                "targeted_questions": [
                    {"question": "What were you doing near Peachtree St?", "relevant_charge_id": "charge_001", "relevant_element": "knowingly possessed", "priority": "MUST_ASK"},
                ],
                "client_responses": {"msg_001": "I was walking from a bar. I didn't drop anything."},
                "charges": [
                    {"charge_id": "charge_001", "offense_title": "Possession of Cocaine", "elements": ["knowingly possessed", "controlled substance (cocaine)"]},
                ],
            })

        assert result["confidence"] is not None
        data = result["data"]
        assert len(data["timeline"]) == 3
        assert len(data["witnesses"]) == 2
        assert len(data["evidence_inventory"]) == 2
        assert data["scene_description"] != ""
        assert len(data["element_coverage"]) == 2
        assert len(data["follow_up_questions"]) == 2

        # Verify element coverage detail
        possession_element = next(
            ec for ec in data["element_coverage"]
            if ec["element"] == "knowingly possessed"
        )
        assert possession_element["client_position"] == "DENIES"

    @pytest.mark.asyncio
    async def test_fact_gatherer_empty_input(self):
        """Test fact gatherer handles missing client data gracefully."""
        agent = FactGathererAgent()
        result = await agent.run({"targeted_questions": [], "client_responses": {}})

        assert result["confidence"] == "LOW"
        data = result["data"]
        assert len(data["timeline"]) == 0
        assert "No client responses" in data["credibility_notes"][0]

    @pytest.mark.asyncio
    async def test_fact_gatherer_confidence_scoring(self):
        """Test confidence calculation logic."""
        agent = FactGathererAgent()

        # Test with high coverage
        output = FactGatheringOutput(
            timeline=[
                TimelineEvent(id="e1", timestamp_description="t", event="e", source="CLIENT_STATEMENT", confidence="HIGH"),
                TimelineEvent(id="e2", timestamp_description="t", event="e", source="CLIENT_STATEMENT", confidence="HIGH"),
                TimelineEvent(id="e3", timestamp_description="t", event="e", source="CLIENT_STATEMENT", confidence="HIGH"),
            ],
            witnesses=[
                WitnessRecord(id="w1", relationship="EYEWITNESS"),
                WitnessRecord(id="w2", relationship="ALIBI"),
            ],
            element_coverage=[
                ElementCoverage(charge_id="c1", element="e1", covered=True, confidence="HIGH"),
                ElementCoverage(charge_id="c1", element="e2", covered=True, confidence="HIGH"),
            ],
        )
        confidence = agent._calculate_confidence(output)
        assert confidence >= 0.7  # High coverage, good timeline and witnesses


class TestCollateralConsequencesAgent:
    """Golden-output tests for the Collateral Consequences Agent."""

    @pytest.mark.asyncio
    async def test_collateral_golden_output(self):
        """Test collateral analysis with cocaine possession case."""
        agent = CollateralConsequencesAgent()

        with patch("src.agents.tier2_intake.collateral_agent.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _COLLATERAL_GOLDEN_RESPONSE

            result = await agent.run({
                "charges": [
                    {"charge_id": "charge_001", "offense_title": "Possession of Cocaine", "statute_section": "O.C.G.A. § 16-13-30(a)"},
                ],
                "personal_circumstances": {
                    "citizenship": "US Citizen",
                    "employment_status": "Employed",
                },
                "client_priorities": ["keeping my job", "avoiding jail"],
            })

        data = result["data"]
        assert len(data["consequences"]) == 3
        assert data["padilla_assessment"]["non_citizen"] is False
        assert data["padilla_assessment"]["advisory_required"] is False
        assert len(data["priority_consequences"]) == 1
        assert "First Offender" in data["plea_strategy_impact"]

    @pytest.mark.asyncio
    async def test_collateral_no_charges(self):
        """Test collateral agent handles missing charges gracefully."""
        agent = CollateralConsequencesAgent()
        result = await agent.run({"charges": [], "personal_circumstances": {}})

        assert result["confidence"] == "LOW"
        data = result["data"]
        assert len(data["consequences"]) == 0

    @pytest.mark.asyncio
    async def test_collateral_padilla_noncitizen(self):
        """Test Padilla assessment flags for non-citizen client."""
        agent = CollateralConsequencesAgent()

        padilla_response = dict(_COLLATERAL_GOLDEN_RESPONSE)
        padilla_response["padilla_assessment"] = {
            "non_citizen": True,
            "immigration_status": "LPR",
            "deportation_risk": "CERTAIN",
            "aggravated_felony_risk": False,
            "crime_involving_moral_turpitude": True,
            "controlled_substance_offense": True,
            "firearm_offense": False,
            "domestic_violence_offense": False,
            "advisory_required": True,
            "advisory_summary": "Client is LPR. Cocaine possession triggers deportation.",
        }

        with patch("src.agents.tier2_intake.collateral_agent.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = padilla_response
            result = await agent.run({
                "charges": [{"charge_id": "charge_001", "offense_title": "Possession of Cocaine"}],
                "personal_circumstances": {"citizenship": "LPR"},
            })

        data = result["data"]
        assert data["padilla_assessment"]["advisory_required"] is True
        assert data["padilla_assessment"]["deportation_risk"] == "CERTAIN"


class TestPersonalCircumstancesAgent:
    """Golden-output tests for the Personal Circumstances Agent."""

    @pytest.mark.asyncio
    async def test_personal_golden_output(self):
        """Test personal circumstances with cocaine possession case."""
        agent = PersonalCircumstancesAgent()

        with patch("src.agents.tier2_intake.personal_circumstances.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _PERSONAL_GOLDEN_RESPONSE

            result = await agent.run({
                "client_background": {
                    "citizenship": "US Citizen",
                    "employment_status": "Employed — line cook, 3 years",
                    "housing_status": "Rents apartment, East Atlanta, 2 years",
                    "dependents": 0,
                    "mental_health_history": None,
                    "substance_abuse_history": "Denies regular use",
                    "military_service": False,
                    "education_status": "High school diploma",
                    "prior_record_self_report": "No prior arrests",
                },
                "charges": [
                    {"charge_id": "charge_001", "offense_title": "Possession of Cocaine"},
                ],
            })

        data = result["data"]

        # Bail profile
        assert len(data["bail_profile"]["community_ties"]) == 3
        assert data["bail_profile"]["recommendation"] == "OR"

        # Mitigation
        assert "DRAFT" in data["mitigation_narrative"]["summary"]
        assert len(data["mitigation_narrative"]["favorable_factors"]) >= 3

        # Diversion
        assert len(data["diversion_eligibility"]) == 3
        first_offender = next(
            d for d in data["diversion_eligibility"] if d["program"] == "FIRST_OFFENDER"
        )
        assert first_offender["eligible"] is True
        assert "42-8-60" in first_offender["georgia_authority"]

        # First offender flag
        assert data["first_offender_eligible"] is True

    @pytest.mark.asyncio
    async def test_personal_empty_background(self):
        """Test personal circumstances agent handles empty background."""
        agent = PersonalCircumstancesAgent()
        result = await agent.run({"client_background": {}})

        assert result["confidence"] == "LOW"
        data = result["data"]
        assert "Insufficient" in data["mitigation_narrative"]["summary"]

    @pytest.mark.asyncio
    async def test_personal_confidence_scoring(self):
        """Test confidence calculation with rich vs sparse data."""
        agent = PersonalCircumstancesAgent()

        rich_output = PersonalCircumstancesOutput(
            bail_profile=BailProfile(
                community_ties=[
                    CommunityTie(category="EMPLOYMENT", description="Employed", strength="STRONG"),
                    CommunityTie(category="FAMILY", description="Family nearby", strength="STRONG"),
                    CommunityTie(category="RESIDENCE", description="Stable housing", strength="MODERATE"),
                ],
            ),
            mitigation_narrative=MitigationNarrative(
                summary="A" * 120,  # long enough summary
            ),
            diversion_eligibility=[
                DiversionEligibility(program="FIRST_OFFENDER", eligible=True, basis="Eligible"),
                DiversionEligibility(program="PRETRIAL_DIVERSION", eligible=True, basis="Eligible"),
                DiversionEligibility(program="DRUG_COURT", eligible=True, basis="Eligible"),
            ],
        )

        rich_bg = {
            "citizenship": "US Citizen",
            "employment_status": "Employed",
            "housing_status": "Rents",
            "education_status": "HS diploma",
            "prior_record_self_report": "None",
        }

        confidence = agent._calculate_confidence(rich_output, rich_bg)
        assert confidence >= 0.75  # Rich data = high confidence


# ---------------------------------------------------------------------------
# Graph integration test
# ---------------------------------------------------------------------------


class TestIntakeSubAgentsNode:
    """Test the intake_sub_agents_node graph wiring."""

    @pytest.mark.asyncio
    async def test_intake_sub_agents_node_runs(self):
        """Test that the intake sub-agents node dispatches all three agents."""
        from src.agents.graph import intake_sub_agents_node

        state = {
            "case_id": "test_case_001",
            "case_state": {
                "jurisdiction": "GA",
                "charge_processing": {
                    "data": {
                        "charges": [
                            {
                                "charge_id": "charge_001",
                                "offense_title": "Possession of Cocaine",
                                "elements": ["knowingly possessed", "controlled substance"],
                            },
                        ],
                    },
                },
                "intake_summary": {
                    "facts": [],
                    "transcript": [{"id": "msg_001", "content": "I was walking home"}],
                    "personal_circumstances": {
                        "citizenship": "US Citizen",
                        "employment_status": "Employed",
                    },
                    "unanswered_questions": [],
                    "priorities_and_concerns": ["keeping my job"],
                },
            },
            "current_stage": "INTAKE_IN_PROGRESS",
            "error": None,
        }

        with patch("src.agents.tier2_intake.fact_gatherer.call_llm", new_callable=AsyncMock) as mock_fact, \
             patch("src.agents.tier2_intake.collateral_agent.call_llm", new_callable=AsyncMock) as mock_coll, \
             patch("src.agents.tier2_intake.personal_circumstances.call_llm", new_callable=AsyncMock) as mock_pers:

            mock_fact.return_value = _FACT_GATHERER_GOLDEN_RESPONSE
            mock_coll.return_value = _COLLATERAL_GOLDEN_RESPONSE
            mock_pers.return_value = _PERSONAL_GOLDEN_RESPONSE

            result = await intake_sub_agents_node(state)

        assert result["current_stage"] == "INTAKE_COMPLETE"
        assert "fact_gathering" in result["case_state"]
        assert "collateral_consequences" in result["case_state"]
        assert "personal_circumstances" in result["case_state"]

        # Verify each result has data
        assert "data" in result["case_state"]["fact_gathering"]
        assert "data" in result["case_state"]["collateral_consequences"]
        assert "data" in result["case_state"]["personal_circumstances"]
