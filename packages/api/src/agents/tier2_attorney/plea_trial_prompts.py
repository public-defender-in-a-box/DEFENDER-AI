"""Prompts for the Plea/Trial Assessment Agent: versioned files in
src/prompts/plea_trial_analyst/. The user prompt is the ``analysis`` template with
one of each pair of optional sections filled in."""

import json

from src.prompts import Prompt, compose_version, load_prompt


def _load(name: str) -> Prompt:
    return load_prompt(f"plea_trial_analyst.{name}", "v1")


SYSTEM = _load("system")
ANALYSIS = _load("analysis")
_ATTORNEY = _load("attorney_inputs")
_NO_ATTORNEY = _load("no_attorney_inputs")
_PLEA_OFFER = _load("plea_offer")
_NO_PLEA_OFFER = _load("no_plea_offer")
_SUPPRESSION = _load("suppression_motion")


def _dump(value: object) -> str:
    return json.dumps(value, indent=2, default=str)


def build_plea_trial_user_prompt(case_data: dict) -> tuple[str, str]:
    """Build the user prompt; return it with the composite version of the files used."""
    used = [SYSTEM, ANALYSIS]

    attorney_inputs = case_data.get("attorney_assessments", {})
    if attorney_inputs:
        attorney_section = _ATTORNEY.text.format(attorney_inputs=_dump(attorney_inputs))
        used.append(_ATTORNEY)
    else:
        attorney_section = _NO_ATTORNEY.text
        used.append(_NO_ATTORNEY)

    plea_offer = case_data.get("plea_offer", {})
    if plea_offer:
        plea_section = _PLEA_OFFER.text.format(plea_offer=_dump(plea_offer))
        used.append(_PLEA_OFFER)
    else:
        plea_section = _NO_PLEA_OFFER.text
        used.append(_NO_PLEA_OFFER)

    suppression_section = ""
    suppression_motions = [
        m
        for m in case_data.get("draft_motions", [])
        if "suppress" in str(m.get("motion_type", "")).lower()
    ]
    if suppression_motions:
        suppression_section = _SUPPRESSION.text.format(
            suppression_motions=_dump(suppression_motions)
        )
        used.append(_SUPPRESSION)

    prompt = ANALYSIS.text.format(
        charges=_dump(case_data.get("charges", [])),
        rights_violations=_dump(case_data.get("rights_violations", [])),
        intake_summary=_dump(case_data.get("intake_summary", {})),
        legal_research=_dump(case_data.get("legal_research", {})),
        collateral_consequences=_dump(case_data.get("collateral_consequences", {})),
        brady_analysis=_dump(case_data.get("brady_analysis", {})),
        plea_section=plea_section,
        attorney_section=attorney_section,
        suppression_section=suppression_section,
    )
    return prompt, compose_version(*used)
