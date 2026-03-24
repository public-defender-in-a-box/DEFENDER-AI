"""Tests for research agents against the Marcus Deon Williams case.

Test case:
- Count 1: Possession of Controlled Substance (Alprazolam/Xanax), OCGA 16-13-30(j)(1)
- Count 2: Obstruction of Law Enforcement Officer, OCGA 16-10-24(a)
- Key facts: parking lot known for narcotics, nervous behavior, hand in pocket,
  officers approached, pat-down attempted, defendant pulled away, brief struggle,
  4 Xanax tablets found in jacket pocket, Miranda given and invoked
- Constitutional issues: reasonable suspicion for initial stop, reasonable
  suspicion for pat-down, fruit of poisonous tree, Miranda invocation
"""

import pytest

from src.agents.tier2_research.ga_criminal_case_law import GACriminalCaseLawAgent
from src.agents.tier2_research.constitutional_case_law import ConstitutionalCaseLawAgent
from src.agents.tier2_research.ga_statutes_agent import GAStatutesAgent
from src.agents.tier2_research.citation_verification import CitationVerificationAgent
from src.agents.tier2_research.research_orchestrator import ResearchOrchestrator
from src.models.research import (
    GACriminalCaseLawOutput,
    ConstitutionalCaseLawOutput,
    GAStatutesOutput,
    CitationVerificationOutput,
    CombinedResearchOutput,
)


# ---------- Williams case test fixtures ----------


@pytest.fixture
def williams_charges() -> list[dict]:
    """Parsed charges for Marcus Deon Williams."""
    return [
        {
            "charge_id": "williams_001",
            "statute_section": "OCGA 16-13-30(j)(1)",
            "offense_title": "Possession of Controlled Substance (Alprazolam)",
            "degree": "Felony",
            "elements": [
                "Unlawful possession",
                "Of a controlled substance (Schedule IV — Alprazolam)",
                "Knowingly",
            ],
            "penalty_range": {
                "minimum_months": 12,
                "maximum_months": 36,
                "fine_min": 0,
                "fine_max": 5000,
                "mandatory_minimum": False,
                "probation_eligible": True,
            },
            "enhancements": [],
            "procedural_requirements": [],
        },
        {
            "charge_id": "williams_002",
            "statute_section": "OCGA 16-10-24(a)",
            "offense_title": "Obstruction of Law Enforcement Officer",
            "degree": "Misdemeanor",
            "elements": [
                "Knowingly and willfully",
                "Obstructed or hindered",
                "A law enforcement officer",
                "In the lawful discharge of official duties",
            ],
            "penalty_range": {
                "minimum_months": 0,
                "maximum_months": 12,
                "fine_min": 0,
                "fine_max": 1000,
                "mandatory_minimum": False,
                "probation_eligible": True,
            },
            "enhancements": [],
            "procedural_requirements": [],
        },
    ]


@pytest.fixture
def williams_factual_allegations() -> list[dict]:
    """Factual allegations from the Williams charging documents."""
    return [
        {
            "id": "fa_001",
            "allegation": (
                "Officers observed the defendant in a parking lot known for "
                "narcotics activity. Defendant appeared nervous and placed his "
                "hand in his jacket pocket."
            ),
            "related_charge_ids": ["williams_001", "williams_002"],
            "related_elements": ["Reasonable suspicion"],
            "date_of_allegation": "2024-01-15",
            "location": "Parking lot, Fulton County, GA",
        },
        {
            "id": "fa_002",
            "allegation": (
                "Officers approached the defendant for a consensual encounter. "
                "Based on nervous behavior and hand in pocket, officers attempted "
                "a pat-down for weapons."
            ),
            "related_charge_ids": ["williams_001"],
            "related_elements": ["Terry stop", "Pat-down"],
        },
        {
            "id": "fa_003",
            "allegation": (
                "Defendant pulled away from officers during pat-down attempt, "
                "leading to a brief physical struggle."
            ),
            "related_charge_ids": ["williams_002"],
            "related_elements": ["Obstruction"],
        },
        {
            "id": "fa_004",
            "allegation": (
                "Following the struggle, officers recovered 4 Xanax tablets "
                "(Alprazolam) from the defendant's jacket pocket."
            ),
            "related_charge_ids": ["williams_001"],
            "related_elements": ["Possession", "Controlled substance"],
        },
        {
            "id": "fa_005",
            "allegation": (
                "Defendant was read Miranda rights and invoked his right to "
                "remain silent."
            ),
            "related_charge_ids": ["williams_001", "williams_002"],
            "related_elements": ["Miranda"],
        },
    ]


@pytest.fixture
def williams_rights_flags() -> list[dict]:
    """Rights violation flags from the Rights Scanner."""
    return [
        {
            "amendment": "fourth_amendment",
            "category": "UNREASONABLE_STOP",
            "description": (
                "Initial detention may lack reasonable suspicion. Presence in a "
                "parking lot and nervousness alone may be insufficient to justify "
                "a Terry stop."
            ),
            "confidence": "MEDIUM",
            "facts": [
                "Defendant was in a parking lot known for narcotics",
                "Appeared nervous",
                "Hand in jacket pocket",
            ],
        },
        {
            "amendment": "fourth_amendment",
            "category": "UNREASONABLE_SEARCH",
            "description": (
                "Pat-down for weapons may lack independent reasonable suspicion "
                "that defendant was armed and dangerous. Nervousness and hand in "
                "pocket may be insufficient."
            ),
            "confidence": "MEDIUM",
            "facts": [
                "Officers attempted pat-down based on nervous behavior",
                "Hand in pocket cited as basis",
                "No specific articulable facts suggesting weapon",
            ],
        },
        {
            "amendment": "fourth_amendment",
            "category": "FRUIT_OF_POISONOUS_TREE",
            "description": (
                "If the initial stop or pat-down was unlawful, the Xanax found "
                "in defendant's pocket may be subject to suppression as fruit "
                "of the poisonous tree."
            ),
            "confidence": "MEDIUM",
            "facts": [
                "Xanax found during/after pat-down",
                "Discovery directly resulted from the stop and frisk",
            ],
        },
        {
            "amendment": "fifth_amendment",
            "category": "MIRANDA",
            "description": (
                "Defendant invoked Miranda rights. Any subsequent questioning "
                "must cease. Verify that invocation was honored."
            ),
            "confidence": "HIGH",
            "facts": [
                "Miranda given",
                "Defendant invoked right to silence",
            ],
        },
    ]


@pytest.fixture
def williams_defense_theories() -> list[str]:
    """Defense theories from pre-interview research."""
    return [
        "Motion to suppress — lack of reasonable suspicion for initial Terry stop",
        "Motion to suppress — lack of reasonable suspicion for pat-down (no basis to believe armed)",
        "Fruit of the poisonous tree — suppress Xanax evidence if stop/frisk was unlawful",
        "Obstruction charge fails if underlying police conduct was unlawful",
        "Constructive vs actual possession — were the tablets really in his control",
    ]


@pytest.fixture
def williams_case_summary() -> str:
    """Brief case summary for the Williams case."""
    return (
        "Marcus Deon Williams was approached by officers in a parking lot known "
        "for narcotics activity. Officers observed nervous behavior and the "
        "defendant placing his hand in his jacket pocket. Officers attempted a "
        "pat-down, during which the defendant pulled away, leading to a brief "
        "struggle. Officers recovered 4 Xanax (Alprazolam) tablets from the "
        "defendant's jacket pocket. Defendant was charged with Possession of "
        "Controlled Substance (OCGA 16-13-30(j)(1)) and Obstruction of Law "
        "Enforcement Officer (OCGA 16-10-24(a)). Miranda rights were administered "
        "and the defendant invoked his right to remain silent."
    )


@pytest.fixture
def williams_full_input(
    williams_charges,
    williams_factual_allegations,
    williams_rights_flags,
    williams_defense_theories,
    williams_case_summary,
) -> dict:
    """Complete input for the research orchestrator."""
    return {
        "case_id": "williams_test_001",
        "charges": williams_charges,
        "factual_allegations": williams_factual_allegations,
        "rights_violation_flags": williams_rights_flags,
        "defense_theories": williams_defense_theories,
        "case_summary": williams_case_summary,
        "enhancements": [],
        "defendant_info": {
            "name": "Marcus Deon Williams",
            "prior_record": "unknown",
        },
    }


# ---------- Model validation tests ----------


class TestResearchModels:
    """Test that Pydantic models validate correctly."""

    def test_ga_criminal_case_law_output_empty(self):
        output = GACriminalCaseLawOutput()
        assert output.research_results == []

    def test_ga_criminal_case_law_output_populated(self):
        output = GACriminalCaseLawOutput(
            research_results=[
                {
                    "legal_issue": "Reasonable suspicion for Terry stop",
                    "issue_source": "rights_violation_flag",
                    "queries_run": ["Georgia reasonable suspicion Terry stop"],
                    "cases_found": [
                        {
                            "case_name": "State v. Example",
                            "citation": "300 Ga. App. 123 (2019)",
                            "court": "Court of Appeals of Georgia",
                            "date": "2019-06-15",
                            "holding": "The court held that nervousness alone is insufficient",
                            "factual_similarity": "high",
                            "similarity_explanation": "Similar parking lot scenario",
                            "favorable": True,
                            "relevance_to_client": "Supports motion to suppress",
                            "source": "COURTLISTENER",
                            "verification_status": "PENDING",
                        }
                    ],
                }
            ]
        )
        assert len(output.research_results) == 1
        assert len(output.research_results[0].cases_found) == 1
        assert output.research_results[0].cases_found[0].favorable is True

    def test_constitutional_output(self):
        output = ConstitutionalCaseLawOutput(
            constitutional_research=[
                {
                    "amendment": "fourth_amendment",
                    "issue": "Reasonable suspicion for investigative detention",
                    "legal_standard": "Terry v. Ohio framework",
                    "foundational_authority": [
                        {
                            "case_name": "Terry v. Ohio",
                            "citation": "392 U.S. 1 (1968)",
                            "court": "Supreme Court of the United States",
                            "holding": "Officers may briefly stop and frisk...",
                            "source": "KNOWN_AUTHORITY",
                            "verification_status": "PENDING",
                        }
                    ],
                    "circuit_authority": [],
                    "state_authority": [],
                    "application_to_client": "Analysis here",
                    "strength_assessment": "strong",
                    "strength_explanation": "Strong argument on these facts",
                }
            ]
        )
        assert len(output.constitutional_research) == 1
        assert output.constitutional_research[0].amendment == "fourth_amendment"

    def test_ga_statutes_output(self):
        output = GAStatutesOutput(
            charged_offenses=[
                {
                    "statute": "OCGA 16-13-30(j)(1)",
                    "title": "Possession of Controlled Substance",
                    "full_text": "It is unlawful...",
                    "elements": [
                        {
                            "element": "Possession",
                            "definition": "Actual or constructive",
                            "document_support": "Found in jacket pocket",
                        }
                    ],
                    "lesser_included": [],
                    "penalties": {
                        "imprisonment_range": "1-3 years",
                        "fine_range": "Up to $5,000",
                        "mandatory_minimum": "none",
                        "probation_eligible": True,
                    },
                }
            ],
            diversion_options=[
                {
                    "program": "First Offender Act",
                    "statute": "OCGA 42-8-60",
                    "eligibility_requirements": "No prior felony",
                    "client_eligible": "unknown",
                    "eligibility_notes": "Need to verify prior record",
                    "benefits": "No conviction on record",
                    "risks": "Max sentence if revoked",
                }
            ],
        )
        assert len(output.charged_offenses) == 1
        assert len(output.diversion_options) == 1

    def test_citation_verification_output(self):
        output = CitationVerificationOutput(
            verification_results=[
                {
                    "original_citation": "Terry v. Ohio, 392 U.S. 1 (1968)",
                    "citation_type": "case",
                    "source_agent": "constitutional_case_law",
                    "verification_status": "VERIFIED",
                    "verification_method": "CourtListener API",
                    "good_law_status": "GOOD_LAW",
                    "negative_treatment": [],
                    "confidence": 0.95,
                    "notes": "Landmark case, well-established",
                }
            ],
            summary={
                "total_citations": 1,
                "verified": 1,
                "unverified": 0,
                "holding_mismatch": 0,
                "overruled": 0,
                "superseded": 0,
                "citation_errors": 0,
            },
        )
        assert output.summary.total_citations == 1
        assert output.summary.verified == 1

    def test_combined_research_output(self):
        output = CombinedResearchOutput()
        assert output.ga_criminal_case_law.research_results == []
        assert output.constitutional_case_law.constitutional_research == []
        assert output.ga_statutes.charged_offenses == []
        assert output.citation_verification.verification_results == []
        assert output.cost_report.total_cost == 0.0


# ---------- Agent unit tests ----------


class TestGACriminalCaseLawAgent:
    """Test the GA Criminal Case Law Agent."""

    def test_agent_metadata(self):
        agent = GACriminalCaseLawAgent()
        assert agent.agent_id == "ga_criminal_case_law"
        assert agent.agent_name == "GA Criminal Case Law Agent"

    @pytest.mark.asyncio
    async def test_run_returns_wrapped_output(self, williams_full_input):
        agent = GACriminalCaseLawAgent()
        result = await agent.run(williams_full_input)

        assert "data" in result
        assert "confidence" in result
        assert result["source"] == "ga_criminal_case_law"
        assert "timestamp" in result
        assert "research_results" in result["data"]

    @pytest.mark.asyncio
    async def test_run_covers_all_legal_issues(self, williams_full_input):
        agent = GACriminalCaseLawAgent()
        result = await agent.run(williams_full_input)

        research = result["data"]["research_results"]
        # Should have results for charges + rights flags + defense theories
        assert len(research) > 0

        # Each result should have the required structure
        for issue in research:
            assert "legal_issue" in issue
            assert "issue_source" in issue
            assert "queries_run" in issue
            assert "cases_found" in issue


class TestConstitutionalCaseLawAgent:
    """Test the Constitutional Case Law Agent."""

    def test_agent_metadata(self):
        agent = ConstitutionalCaseLawAgent()
        assert agent.agent_id == "constitutional_case_law"
        assert agent.agent_name == "Constitutional Law Case Law Agent"

    @pytest.mark.asyncio
    async def test_run_returns_wrapped_output(self, williams_full_input):
        agent = ConstitutionalCaseLawAgent()
        result = await agent.run(williams_full_input)

        assert "data" in result
        assert "confidence" in result
        assert result["source"] == "constitutional_case_law"
        assert "constitutional_research" in result["data"]

    @pytest.mark.asyncio
    async def test_run_covers_constitutional_issues(self, williams_full_input):
        agent = ConstitutionalCaseLawAgent()
        result = await agent.run(williams_full_input)

        research = result["data"]["constitutional_research"]
        assert len(research) > 0

        for issue in research:
            assert "amendment" in issue
            assert "issue" in issue
            assert "legal_standard" in issue
            assert "foundational_authority" in issue
            assert "circuit_authority" in issue
            assert "state_authority" in issue


class TestGAStatutesAgent:
    """Test the GA Statutes Agent."""

    def test_agent_metadata(self):
        agent = GAStatutesAgent()
        assert agent.agent_id == "ga_statutes_agent"
        assert agent.agent_name == "GA Criminal Statutes Agent"

    @pytest.mark.asyncio
    async def test_run_returns_wrapped_output(self, williams_full_input):
        agent = GAStatutesAgent()
        result = await agent.run(williams_full_input)

        assert "data" in result
        assert "confidence" in result
        assert result["source"] == "ga_statutes_agent"

        data = result["data"]
        assert "charged_offenses" in data
        assert "diversion_options" in data
        assert "procedural_requirements" in data

    @pytest.mark.asyncio
    async def test_run_analyzes_both_charges(self, williams_full_input):
        agent = GAStatutesAgent()
        result = await agent.run(williams_full_input)

        offenses = result["data"]["charged_offenses"]
        # Should have analysis for both possession and obstruction
        assert len(offenses) >= 2


class TestCitationVerificationAgent:
    """Test the Citation Verification Agent."""

    def test_agent_metadata(self):
        agent = CitationVerificationAgent()
        assert agent.agent_id == "citation_verification"
        assert agent.agent_name == "Citation Verification Agent"

    @pytest.mark.asyncio
    async def test_run_with_sample_citations(self):
        agent = CitationVerificationAgent()
        input_data = {
            "ga_case_law_output": {
                "research_results": [
                    {
                        "legal_issue": "test",
                        "cases_found": [
                            {
                                "case_name": "Terry v. Ohio",
                                "citation": "392 U.S. 1 (1968)",
                                "court": "Supreme Court of the United States",
                                "holding": "Stop and frisk permissible...",
                            }
                        ],
                    }
                ]
            },
            "constitutional_output": {"constitutional_research": []},
            "statutes_output": {
                "charged_offenses": [
                    {
                        "statute": "OCGA 16-13-30(j)(1)",
                        "full_text": "Possession of controlled substance...",
                    }
                ],
                "diversion_options": [],
                "procedural_requirements": [],
            },
        }

        result = await agent.run(input_data)

        assert "data" in result
        assert "verification_results" in result["data"]
        assert "summary" in result["data"]

        summary = result["data"]["summary"]
        assert summary["total_citations"] > 0

    @pytest.mark.asyncio
    async def test_run_empty_input(self):
        agent = CitationVerificationAgent()
        result = await agent.run({
            "ga_case_law_output": {},
            "constitutional_output": {},
            "statutes_output": {},
        })

        assert result["data"]["summary"]["total_citations"] == 0


# ---------- Integration test: full research pipeline ----------


class TestResearchOrchestrator:
    """Test the full research pipeline."""

    def test_agent_metadata(self):
        orch = ResearchOrchestrator()
        assert orch.agent_id == "research_orchestrator"

    @pytest.mark.asyncio
    async def test_full_pipeline(self, williams_full_input):
        """Run the full research pipeline against the Williams case.

        This is the main integration test. It calls real APIs (CourtListener,
        Anthropic) so it may take a while and costs money.
        """
        orchestrator = ResearchOrchestrator()
        result = await orchestrator.run(williams_full_input)

        assert "data" in result
        assert "confidence" in result
        assert result["source"] == "research_orchestrator"

        data = result["data"]

        # All four agent outputs should be present
        assert "ga_criminal_case_law" in data
        assert "constitutional_case_law" in data
        assert "ga_statutes" in data
        assert "citation_verification" in data
        assert "cost_report" in data

        # GA Case Law should have research results
        ga_research = data["ga_criminal_case_law"]
        assert "research_results" in ga_research

        # Constitutional should have constitutional research
        const_research = data["constitutional_case_law"]
        assert "constitutional_research" in const_research

        # Statutes should have charged offenses
        statutes = data["ga_statutes"]
        assert "charged_offenses" in statutes
        assert "diversion_options" in statutes

        # Verification should have results and summary
        verification = data["citation_verification"]
        assert "verification_results" in verification
        assert "summary" in verification

        # Cost report should be present
        cost = data["cost_report"]
        assert "total_cost" in cost
        assert "courtlistener_calls" in cost

        # Print summary for manual review
        print(f"\n--- Williams Case Research Results ---")
        print(f"GA Case Law issues researched: {len(ga_research.get('research_results', []))}")
        print(
            f"Constitutional issues researched: "
            f"{len(const_research.get('constitutional_research', []))}"
        )
        print(f"Charged offenses analyzed: {len(statutes.get('charged_offenses', []))}")
        print(f"Diversion options found: {len(statutes.get('diversion_options', []))}")
        print(f"Citations verified: {verification.get('summary', {}).get('total_citations', 0)}")
        print(f"  - Verified: {verification.get('summary', {}).get('verified', 0)}")
        print(f"  - Unverified: {verification.get('summary', {}).get('unverified', 0)}")
        print(f"Total cost: ${cost.get('total_cost', 0):.4f}")
        print(f"CourtListener calls: {cost.get('courtlistener_calls', 0)}")
