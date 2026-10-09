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

from unittest.mock import AsyncMock, patch

import pytest

from src.services import measurements
from src.services.courtlistener import CourtListenerError
from src.services.model_gateway import (
    AuthError,
    RefusalError,
    SchemaMismatchError,
    TransportError,
    TruncatedResponseError,
    using_fixtures,
)
from src.services.model_gateway.testing import FakeCallModel

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
                "Defendant was read Miranda rights and invoked his right to " "remain silent."
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


# ---------- Agent tests (canned model and CourtListener responses) ----------
#
# These used to call the live Anthropic and CourtListener APIs and pass only because
# the agents swallowed every error (PHASE_1_MODEL_GATEWAY.md §3.3). They now run
# against canned responses validated by the agents' response models; the live path
# is covered by the recorded replay test at the end.

_GA = "src.agents.tier2_research.ga_criminal_case_law.call_model"
_CONST = "src.agents.tier2_research.constitutional_case_law.call_model"
_STAT = "src.agents.tier2_research.ga_statutes_agent.call_model"
_VERIFY = "src.agents.tier2_research.citation_verification.call_model"

SYN_CASE = {
    "case_name": "Synthetic v. State",
    "citation": "900 Ga. App. 100 (2020)",
    "court": "Court of Appeals of Georgia",
    "date_filed": "2020-05-01",
    "snippet": "nervousness alone does not supply reasonable suspicion",
    "cluster_id": 9000001,
}


def _analyzed(name: str = "Synthetic v. State", citation: str = "900 Ga. App. 100 (2020)"):
    return {
        "case_name": name,
        "citation": citation,
        "court": "Court of Appeals of Georgia",
        "date": "2020-05-01",
        "holding": "Nervousness alone does not supply reasonable suspicion.",
        "factual_similarity": "high",
        "similarity_explanation": "Parking-lot stop on nervousness.",
        "favorable": True,
        "relevance_to_client": "Supports suppression.",
    }


def _search(results=None):
    return AsyncMock(return_value=[SYN_CASE] if results is None else results)


class TestGACriminalCaseLawAgent:
    """Test the GA Criminal Case Law Agent."""

    def test_agent_metadata(self):
        agent = GACriminalCaseLawAgent()
        assert agent.agent_id == "ga_criminal_case_law"
        assert agent.agent_name == "GA Criminal Case Law Agent"

    @pytest.mark.asyncio
    async def test_run_returns_wrapped_output(self, williams_full_input):
        plan = {
            "issue_queries": [
                {
                    "legal_issue": "Reasonable suspicion for the initial stop",
                    "issue_source": "rights_violation_flag",
                    "queries": ["reasonable suspicion nervousness parking lot"],
                },
                {
                    "legal_issue": "Obstruction requires lawful discharge of duties",
                    "issue_source": "charge",
                    "queries": ["obstruction lawful discharge"],
                },
            ]
        }
        fake = FakeCallModel(plan, {"cases": [_analyzed()]}, {"cases": []})
        agent = GACriminalCaseLawAgent()
        agent._cl_client.search_opinions = _search()
        with patch(_GA, new=fake):
            result = await agent.run(williams_full_input)

        assert result["source"] == "ga_criminal_case_law"
        research = result["data"]["research_results"]
        assert [r["legal_issue"] for r in research] == [
            "Reasonable suspicion for the initial stop",
            "Obstruction requires lawful discharge of duties",
        ]
        (case,) = research[0]["cases_found"]
        assert case["source"] == "COURTLISTENER"
        assert case["verification_status"] == "PENDING"
        assert research[1]["cases_found"] == []
        assert fake.prompt_ids == [
            "ga_criminal_case_law.query_generation",
            "ga_criminal_case_law.analysis",
            "ga_criminal_case_law.analysis",
        ]
        # Queries get the Georgia qualifier and the Georgia courts.
        call = agent._cl_client.search_opinions.await_args_list[0]
        assert call.kwargs["query"].startswith("Georgia ")
        assert set(call.kwargs["court_ids"]) == {"ga", "gactapp"}

    @pytest.mark.asyncio
    async def test_query_generation_failure_raises(self, williams_full_input):
        """No fallback queries: a failed model call fails the agent."""
        agent = GACriminalCaseLawAgent()
        agent._cl_client.search_opinions = _search()
        with patch(_GA, new=FakeCallModel(TransportError("overloaded"))):
            with pytest.raises(TransportError):
                await agent.run(williams_full_input)
        agent._cl_client.search_opinions.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_analysis_failure_raises(self, williams_full_input):
        """No unanalyzed fallback (it used to mark every raw result favorable)."""
        plan = {
            "issue_queries": [
                {"legal_issue": "x", "issue_source": "charge", "queries": ["q"]},
            ]
        }
        agent = GACriminalCaseLawAgent()
        agent._cl_client.search_opinions = _search()
        with patch(_GA, new=FakeCallModel(plan, RefusalError("refused"))):
            with pytest.raises(RefusalError):
                await agent.run(williams_full_input)

    @pytest.mark.asyncio
    async def test_search_failure_raises(self, williams_full_input):
        plan = {
            "issue_queries": [
                {"legal_issue": "x", "issue_source": "charge", "queries": ["q"]},
            ]
        }
        agent = GACriminalCaseLawAgent()
        agent._cl_client.search_opinions = AsyncMock(
            side_effect=CourtListenerError("CourtListener GET /search/ returned 503", status=503)
        )
        with patch(_GA, new=FakeCallModel(plan)):
            with pytest.raises(CourtListenerError):
                await agent.run(williams_full_input)


FRAMEWORK = {
    "circuit_authority": [],
    "state_authority": [
        {
            "case_name": "Synthetic v. State",
            "citation": "900 Ga. App. 100 (2020)",
            "court": "Court of Appeals of Georgia",
            "date": "2020-05-01",
            "holding": "Nervousness alone is insufficient.",
            "source": "COURTLISTENER",
            "verification_status": "PENDING",
        }
    ],
    "application_to_client": "The stop rested on nervousness and location.",
    "strength_assessment": "moderate",
    "strength_explanation": "Location plus nervousness is a close call.",
}


class TestConstitutionalCaseLawAgent:
    """Test the Constitutional Case Law Agent."""

    def test_agent_metadata(self):
        agent = ConstitutionalCaseLawAgent()
        assert agent.agent_id == "constitutional_case_law"
        assert agent.agent_name == "Constitutional Law Case Law Agent"

    @pytest.mark.asyncio
    async def test_run_covers_constitutional_issues(self, williams_full_input):
        identify = {
            "constitutional_issues": [
                {
                    "amendment": "fourth_amendment",
                    "issue": "Unreasonable search and seizure",
                    "legal_standard": "Terry stop requires reasonable suspicion",
                    "foundational_cases": [
                        {
                            "case_name": "Terry v. Ohio",
                            "citation": "392 U.S. 1 (1968)",
                            "holding": "Brief stops require reasonable suspicion.",
                        }
                    ],
                    "circuit_queries": ["Terry stop reasonable suspicion"],
                    "state_queries": ["Georgia Terry stop"],
                }
            ]
        }
        fake = FakeCallModel(identify, FRAMEWORK)
        agent = ConstitutionalCaseLawAgent()
        agent._cl_client.search_opinions = _search()
        with patch(_CONST, new=fake):
            result = await agent.run(williams_full_input)

        assert result["source"] == "constitutional_case_law"
        (issue,) = result["data"]["constitutional_research"]
        assert issue["amendment"] == "fourth_amendment"
        assert issue["foundational_authority"][0]["source"] == "KNOWN_AUTHORITY"
        assert issue["state_authority"][0]["citation"] == "900 Ga. App. 100 (2020)"
        assert issue["strength_assessment"] == "moderate"
        courts = [c.kwargs["court_ids"] for c in agent._cl_client.search_opinions.await_args_list]
        assert courts == [["ca11"], ["ga", "gactapp"]]

    @pytest.mark.asyncio
    async def test_framework_failure_raises(self, williams_full_input):
        """No empty-framework fallback."""
        identify = {
            "constitutional_issues": [
                {
                    "amendment": "fifth_amendment",
                    "issue": "Miranda invocation",
                    "legal_standard": "Questioning must cease",
                    "foundational_cases": [],
                    "circuit_queries": [],
                    "state_queries": [],
                }
            ]
        }
        agent = ConstitutionalCaseLawAgent()
        agent._cl_client.search_opinions = _search()
        with patch(_CONST, new=FakeCallModel(identify, TruncatedResponseError("max_tokens"))):
            with pytest.raises(TruncatedResponseError):
                await agent.run(williams_full_input)

    @pytest.mark.asyncio
    async def test_malformed_issue_rejected(self, williams_full_input):
        """The old canned response ("4th Amendment") no longer passes as valid."""
        identify = {
            "constitutional_issues": [
                {
                    "amendment": "4th Amendment",
                    "issue": "x",
                    "legal_standard": "y",
                    "foundational_cases": [],
                    "circuit_queries": [],
                    "state_queries": [],
                }
            ]
        }
        with patch(_CONST, new=FakeCallModel(identify)):
            with pytest.raises(SchemaMismatchError):
                await ConstitutionalCaseLawAgent().run(williams_full_input)


def _offense(statute: str, title: str) -> dict:
    return {
        "statute": statute,
        "title": title,
        "full_text": "(synthetic statutory text)",
        "elements": [
            {"element": "Knowing conduct", "definition": "d", "document_support": "s"},
        ],
        "lesser_included": [],
        "penalties": {
            "imprisonment_range": "up to 12 months",
            "fine_range": "up to $1,000",
            "mandatory_minimum": "none",
            "probation_eligible": True,
        },
    }


STATUTES = {
    "charged_offenses": [
        _offense("O.C.G.A. § 16-13-30(j)(1)", "Possession of Controlled Substance"),
        _offense("O.C.G.A. § 16-10-24(a)", "Obstruction of Law Enforcement"),
    ]
}
DIVERSION = {
    "diversion_options": [
        {
            "program": "First Offender Act",
            "statute": "OCGA 42-8-60",
            "eligibility_requirements": "No prior felony",
            "client_eligible": "unknown",
            "eligibility_notes": "Record unknown",
            "benefits": "No conviction on completion",
            "risks": "Full sentence on revocation",
        }
    ]
}
PROCEDURAL = {
    "procedural_requirements": [
        {
            "requirement": "Speedy trial demand",
            "statute": "OCGA 17-7-170",
            "deadline": "Term of court",
            "notes": "",
        }
    ],
    "recent_amendments": [],
}


class TestGAStatutesAgent:
    """Test the GA Statutes Agent."""

    def test_agent_metadata(self):
        agent = GAStatutesAgent()
        assert agent.agent_id == "ga_statutes_agent"
        assert agent.agent_name == "GA Criminal Statutes Agent"

    @pytest.mark.asyncio
    async def test_run_analyzes_both_charges(self, williams_full_input):
        fake = FakeCallModel(STATUTES, DIVERSION, PROCEDURAL)
        with patch(_STAT, new=fake):
            result = await GAStatutesAgent().run(williams_full_input)

        assert result["source"] == "ga_statutes_agent"
        data = result["data"]
        assert [o["statute"] for o in data["charged_offenses"]] == [
            "O.C.G.A. § 16-13-30(j)(1)",
            "O.C.G.A. § 16-10-24(a)",
        ]
        assert data["diversion_options"][0]["client_eligible"] == "unknown"
        assert data["procedural_requirements"][0]["statute"] == "OCGA 17-7-170"
        assert fake.prompt_ids == [
            "ga_statutes_agent.statutory_analysis",
            "ga_statutes_agent.diversion_analysis",
            "ga_statutes_agent.procedural",
        ]

    @pytest.mark.asyncio
    async def test_failure_is_not_an_empty_analysis(self, williams_full_input):
        with patch(_STAT, new=FakeCallModel(STATUTES, AuthError("401"))):
            with pytest.raises(AuthError):
                await GAStatutesAgent().run(williams_full_input)


VERIFY_INPUT = {
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
STATUTE_OK = {
    "exists": True,
    "content_accurate": True,
    "recently_amended": False,
    "amendment_notes": "",
    "unconstitutional": False,
    "unconstitutional_notes": "",
    "verification_notes": "",
}


def _verifier(found: bool = True) -> CitationVerificationAgent:
    agent = CitationVerificationAgent()
    agent._cl_client.verify_case_exists = AsyncMock(
        return_value={
            "found": found,
            "case_data": {**SYN_CASE, "case_name": "Terry v. Ohio"} if found else None,
            "method": "test",
        }
    )
    agent._cl_client.get_citing_cases = AsyncMock(return_value=[])
    return agent


def _holding(matches: bool) -> dict:
    return {"matches": matches, "explanation": "e", "actual_holding_summary": "s"}


class TestCitationVerificationAgent:
    """Test the Citation Verification Agent."""

    def test_agent_metadata(self):
        agent = CitationVerificationAgent()
        assert agent.agent_id == "citation_verification"
        assert agent.agent_name == "Citation Verification Agent"

    @pytest.mark.asyncio
    async def test_run_with_sample_citations(self):
        fake = FakeCallModel(
            by_prompt={
                "citation_verification.holding_check": _holding(True),
                "citation_verification.statute_verification": STATUTE_OK,
            }
        )
        with patch(_VERIFY, new=fake):
            result = await _verifier().run(VERIFY_INPUT)

        results = {r["citation_type"]: r for r in result["data"]["verification_results"]}
        assert results["case"]["verification_status"] == "VERIFIED"
        assert results["statute"]["verification_status"] == "VERIFIED"
        summary = result["data"]["summary"]
        assert summary["total_citations"] == 2
        assert summary["verified"] == 2

    @pytest.mark.asyncio
    async def test_holding_mismatch_is_reported(self):
        fake = FakeCallModel(
            by_prompt={
                "citation_verification.holding_check": _holding(False),
                "citation_verification.statute_verification": STATUTE_OK,
            }
        )
        with patch(_VERIFY, new=fake):
            result = await _verifier().run(VERIFY_INPUT)
        assert result["data"]["summary"]["holding_mismatch"] == 1

    @pytest.mark.asyncio
    async def test_case_not_found_is_unverified(self):
        fake = FakeCallModel(by_prompt={"citation_verification.statute_verification": STATUTE_OK})
        with patch(_VERIFY, new=fake):
            result = await _verifier(found=False).run(VERIFY_INPUT)
        assert result["data"]["summary"]["unverified"] == 1
        assert "citation_verification.holding_check" not in fake.prompt_ids

    @pytest.mark.asyncio
    async def test_run_empty_input(self):
        agent = CitationVerificationAgent()
        result = await agent.run(
            {
                "ga_case_law_output": {},
                "constitutional_output": {},
                "statutes_output": {},
            }
        )

        assert result["data"]["summary"]["total_citations"] == 0


class TestHoldingCheckFailure:
    """A failed holding check must not count as a verified holding (Phase 1 §3.2)."""

    @pytest.mark.asyncio
    async def test_failed_holding_check_raises(self):
        with patch(_VERIFY, new=FakeCallModel(TransportError("connection reset"))):
            with pytest.raises(TransportError):
                await _verifier().run(VERIFY_INPUT)


# ---------- Research Orchestrator ----------


class TestResearchOrchestrator:
    """Test the full research pipeline."""

    def test_agent_metadata(self):
        orch = ResearchOrchestrator()
        assert orch.agent_id == "research_orchestrator"

    @pytest.mark.asyncio
    async def test_partial_failure_is_recorded_not_hidden(self, williams_full_input):
        """A failed sub-agent is listed with its error type; the others still run."""
        orch = ResearchOrchestrator()
        for agent in (orch._ga_case_law, orch._constitutional):
            agent._cl_client.search_opinions = _search([])
        orch._verifier._cl_client.verify_case_exists = AsyncMock(
            return_value={"found": False, "case_data": None, "method": "test"}
        )
        empty_plan = {"issue_queries": []}
        empty_issues = {"constitutional_issues": []}
        with (
            patch(_GA, new=FakeCallModel(empty_plan)),
            patch(_CONST, new=FakeCallModel(empty_issues)),
            patch(_STAT, new=FakeCallModel(TransportError("overloaded"))),
            patch(_VERIFY, new=FakeCallModel()),
        ):
            result = await orch.run(williams_full_input)

        data = result["data"]
        assert data["failed_agents"] == [
            {"agent_id": "ga_statutes_agent", "error_type": "TransportError", "error": "overloaded"}
        ]
        assert data["ga_statutes"] == {}
        assert data["ga_criminal_case_law"] == {"research_results": []}
        (failure,) = measurements.events(measurements.MeasurementKind.AGENT_FAILURE)
        assert failure.agent_id == "ga_statutes_agent"
        assert failure.payload["error_type"] == "TransportError"

    @pytest.mark.asyncio
    async def test_unexpected_exception_is_not_swallowed(self, williams_full_input):
        """The boundary is narrowed: a bug raises instead of becoming a LOW result."""
        orch = ResearchOrchestrator()
        orch._statutes.run = AsyncMock(side_effect=KeyError("charges"))
        orch._ga_case_law.run = AsyncMock(return_value={"data": {}, "confidence": "HIGH"})
        orch._constitutional.run = AsyncMock(return_value={"data": {}, "confidence": "HIGH"})
        with pytest.raises(KeyError):
            await orch.run(williams_full_input)

    @pytest.mark.asyncio
    @pytest.mark.recorded(
        "ga_criminal_case_law",
        "constitutional_case_law",
        "ga_statutes_agent",
        "citation_verification",
        "courtlistener",
    )
    async def test_full_pipeline(self, williams_full_input):
        """Run the full research pipeline against the Williams case, from recordings.

        Recorded once by a team member (MODEL_GATEWAY_MODE=record, their own keys);
        replayed with no key and no network.
        """
        orchestrator = ResearchOrchestrator()
        with using_fixtures("tests/test_research_agents.py::williams_full_input"):
            result = await orchestrator.run(williams_full_input)

        assert "data" in result
        assert "confidence" in result
        assert result["source"] == "research_orchestrator"

        data = result["data"]
        assert data["failed_agents"] == []
        assert data["ga_criminal_case_law"]["research_results"]
        assert "constitutional_research" in data["constitutional_case_law"]
        assert data["ga_statutes"]["charged_offenses"]
        assert "summary" in data["citation_verification"]
        cost = data["cost_report"]
        assert cost["total_cost"] > 0, "would-be cost of the replayed calls"
        assert cost["billed_cost"] == 0, "a replay spends nothing"
        assert cost["courtlistener_calls"] > 0
