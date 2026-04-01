"""FastAPI endpoints for the Sentencing & Mitigation Agent."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..graph import run_sentencing_analysis
from ..models.inputs import (
    JurisdictionContext,
    OffenseDetails,
    PersonalCircumstances,
    PriorRecord,
    SentencingAgentInput,
)
from ..models.outputs import (
    ComparableSentence,
    DiversionOption,
    GuidelineRange,
    SentencingAgentOutput,
)
from ..nodes.comparable_sentence_lookup import find_comparable_sentences
from ..nodes.diversion_checker import (
    check_drug_court,
    check_pretrial_diversion,
    check_veterans_court,
    conditional_discharge_prelim,
    load_program_directory,
)
from ..nodes.exposure_calculator import calculate_guideline_range

router = APIRouter(prefix="/api/v1/sentencing", tags=["sentencing"])


@router.post("/analyze", response_model=SentencingAgentOutput)
async def analyze_sentencing(input_data: SentencingAgentInput) -> SentencingAgentOutput:
    """Run full sentencing analysis pipeline.

    Returns partial output even if some nodes fail.
    """
    return await run_sentencing_analysis(input_data)


class ExposureRequest(BaseModel):
    jurisdiction_context: JurisdictionContext
    offense_details: OffenseDetails
    criminal_history: PriorRecord
    pretrial_custody_days: int = 0


@router.post("/exposure", response_model=GuidelineRange)
async def calculate_exposure(input_data: ExposureRequest) -> GuidelineRange:
    """Calculate deterministic sentencing exposure.

    Fast endpoint — no LLM calls.
    """
    return calculate_guideline_range(
        offense=input_data.offense_details,
        history=input_data.criminal_history,
        pretrial_custody_days=input_data.pretrial_custody_days,
    )


class DiversionRequest(BaseModel):
    jurisdiction_context: JurisdictionContext
    offense_details: OffenseDetails
    criminal_history: PriorRecord
    personal_circumstances: PersonalCircumstances
    program_availability_overrides: dict[str, bool] = Field(default_factory=dict)


@router.post("/diversion", response_model=list[DiversionOption])
async def check_diversion(input_data: DiversionRequest) -> list[DiversionOption]:
    """Check diversion program availability and eligibility.

    Distinguishes unknown availability from ineligibility.
    """
    from ..models.inputs import CasePhase, SentencingAgentInput

    # Build a minimal SentencingAgentInput for the diversion checker functions
    sentinel_input = SentencingAgentInput(
        case_id="diversion-check",
        case_phase=CasePhase.PRETRIAL,
        jurisdiction_context=input_data.jurisdiction_context,
        offense_details=input_data.offense_details,
        criminal_history=input_data.criminal_history,
        personal_circumstances=input_data.personal_circumstances,
        program_availability_overrides=input_data.program_availability_overrides,
    )

    try:
        directory = load_program_directory()
    except Exception:
        directory = []

    options: list[DiversionOption] = []

    # Conditional discharge
    cd_elig, cd_reasons = conditional_discharge_prelim(input_data.criminal_history)
    options.append(
        DiversionOption(
            program_name="Conditional Discharge",
            statutory_basis="O.C.G.A. § 16-13-2(a)",
            availability_status="confirmed_available",
            preliminary_eligibility=cd_elig,
            eligibility_factors=cd_reasons,
            outcome_if_completed=(
                "Court may dismiss charges without entering a judgment of guilt. "
                "Possible record restriction / sealing review under O.C.G.A. § 35-3-37."
            ),
            typical_duration="Up to 3 years probation (court discretion)",
            conditions=["Reasonable conditions set by court"],
            recommendation_notes="Conditional discharge is one-time only.",
            source_ref="O.C.G.A. § 16-13-2(a)",
        )
    )

    options.append(check_pretrial_diversion(sentinel_input, directory))
    options.append(check_drug_court(sentinel_input, directory))

    vc = check_veterans_court(sentinel_input, directory)
    if vc:
        options.append(vc)

    return options


@router.get("/cases/{case_id}/comparables", response_model=list[ComparableSentence])
async def get_comparables(
    case_id: str,
    county: str = "Clarke",
    circuit: Optional[str] = None,
) -> list[ComparableSentence]:
    """Get comparable sentencing outcomes for a case.

    Uses local seed corpus for matching.
    """
    from ..models.inputs import CasePhase, SentencingAgentInput

    # Build minimal input for the lookup function
    sentinel_input = SentencingAgentInput(
        case_id=case_id,
        case_phase=CasePhase.PRETRIAL,
        jurisdiction_context=JurisdictionContext(county=county, judicial_circuit=circuit),
        offense_details=OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(1)",
            charge_description="Simple possession of marijuana",
        ),
        criminal_history=PriorRecord(has_prior_convictions=False),
        personal_circumstances=PersonalCircumstances(),
    )

    return find_comparable_sentences(sentinel_input)
