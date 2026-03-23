"""Shared test fixtures for case state, plea offers, and mock LLM responses.

Contains fixtures used by both motion drafter and plea/trial analyst tests.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Base case state helpers
# ---------------------------------------------------------------------------


def make_minimal_case_state() -> dict[str, Any]:
    """Bare-minimum case state — just identity and jurisdiction."""
    return {
        "id": "test_case_001",
        "case_id": "test_case_001",
        "jurisdiction": "GA",
        "stage": "CASE_PREP_IN_PROGRESS",
        "attorney_id": "attorney_001",
        "documents": [],
    }


def make_sample_charges() -> list[dict[str, Any]]:
    """Sample charges from the Charge Processing Agent."""
    return [
        {
            "charge_id": "charge_001",
            "statute": "O.C.G.A. § 16-13-30(a)",
            "description": "Possession of a controlled substance (cocaine, <1 oz)",
            "severity": "FELONY",
            "class": "Felony",
            "max_incarceration_years": 15,
            "min_incarceration_years": 1,
            "max_fine": 5000,
            "enhancements": [],
        }
    ]


def make_sample_rights_violations() -> list[dict[str, Any]]:
    """Sample rights violation analysis."""
    return [
        {
            "violation_type": "FOURTH_AMENDMENT",
            "description": (
                "Officer stopped defendant without reasonable articulable suspicion. "
                "Defendant was standing on a public sidewalk and no criminal activity "
                "was observed prior to the stop."
            ),
            "severity": "HIGH",
            "suppression_viable": True,
            "confidence": 0.75,
        }
    ]


def make_sample_intake_summary() -> dict[str, Any]:
    """Sample intake summary."""
    return {
        "defendant_name": "John Doe",
        "age": 28,
        "employment": "Employed full-time — warehouse worker",
        "dependents": 1,
        "prior_record": "No prior criminal record",
        "citizenship_status": "US Citizen",
        "substance_use_history": "Client reports occasional recreational use",
        "mental_health": "No reported issues",
        "housing": "Stable housing — rents apartment",
    }


def make_sample_legal_research() -> dict[str, Any]:
    """Sample legal research output."""
    return {
        "relevant_statutes": [
            {
                "citation": "O.C.G.A. § 16-13-30(a) [VERIFIED]",
                "summary": "Possession of controlled substance — Schedule II",
                "sentencing_range": "1–15 years felony; may be probated",
            },
            {
                "citation": "O.C.G.A. § 42-8-60 [VERIFIED]",
                "summary": "Georgia First Offender Act — eligible if no prior felony",
            },
        ],
        "relevant_case_law": [
            {
                "citation": "State v. Sample, 300 Ga. 123 (2022) [UNVERIFIED]",
                "holding": "Suppression granted where officer lacked RAS for initial stop",
            }
        ],
    }


def make_sample_draft_motions() -> list[dict[str, Any]]:
    """Sample draft motions from the Motion Drafter."""
    return [
        {
            "motion_type": "SUPPRESS",
            "title": "Motion to Suppress Physical Evidence",
            "status": "DRAFT",
            "confidence": 0.75,
            "viability": 0.75,
            "supporting_authority": [
                "O.C.G.A. § 17-5-30 [VERIFIED]",
                "State v. Sample, 300 Ga. 123 (2022) [UNVERIFIED]",
            ],
        }
    ]


def make_sample_brady_analysis() -> dict[str, Any]:
    """Sample Brady analysis."""
    return {
        "potential_brady_material": [
            {
                "description": "Body camera footage may show officer approaching without cause",
                "materiality": "HIGH",
                "status": "REQUESTED",
            }
        ],
        "disclosure_status": "PENDING",
    }


def make_sample_case_state() -> dict[str, Any]:
    """Full case state with charge, intake, and research data.

    Used by motion drafter tests. Contains all upstream agent outputs
    needed for motion drafting but NOT plea/trial-specific fields.
    """
    data = make_minimal_case_state()
    data["charges"] = make_sample_charges()
    data["rights_violations"] = make_sample_rights_violations()
    data["intake_summary"] = make_sample_intake_summary()
    data["legal_research"] = make_sample_legal_research()
    data["collateral_consequences"] = {
        "immigration": {"impact": "NONE", "details": "US Citizen — no immigration consequences"},
        "employment": {"impact": "MEDIUM", "details": "Felony conviction may affect employment"},
        "housing": {"impact": "LOW", "details": "May affect public housing eligibility"},
    }
    data["draft_motions"] = make_sample_draft_motions()
    data["brady_analysis"] = make_sample_brady_analysis()
    return data


# ---------------------------------------------------------------------------
# Plea / Trial specific helpers
# ---------------------------------------------------------------------------


def make_sample_plea_offer() -> dict[str, Any]:
    """Realistic plea offer for the drug possession case.

    Plea to misdemeanor possession under O.C.G.A. § 16-13-30(a).
    12 months probation, $500 fine, substance abuse evaluation.
    No incarceration if probation completed.
    First Offender treatment possible.
    """
    return {
        "offer_date": "2024-02-15",
        "offered_charge": "Misdemeanor possession of a controlled substance",
        "offered_statute": "O.C.G.A. § 16-13-30(a)",
        "original_charges": [
            "Felony possession of a controlled substance — O.C.G.A. § 16-13-30(a)"
        ],
        "terms": {
            "incarceration_months": 0,
            "probation_months": 12,
            "fine_amount": 500.0,
            "community_service_hours": 40,
            "substance_abuse_evaluation": True,
            "treatment_program": True,
        },
        "conditions": [
            "Complete substance abuse evaluation",
            "No new arrests during probation",
            "Random drug testing",
        ],
        "first_offender_eligible": True,
        "expiration": "2024-03-15",
        "prosecutor_notes": "Standard offer for first-time possession under 1 oz",
    }


def make_sample_attorney_assessments() -> dict[str, Any]:
    """Attorney subjective inputs for the plea/trial analysis."""
    return {
        "estimated_acquittal_probability": 0.35,
        "judge_sentencing_tendency": "MODERATE",
        "witness_credibility_assessment": "MODERATE",
        "client_testimony_viability": "MODERATE",
        "jury_pool_assessment": "Fulton County — urban jury pool, generally moderate",
        "plea_negotiation_room": (
            "Likely some room — DA has offered similar deals in comparable cases"
        ),
    }


def make_full_case_data() -> dict[str, Any]:
    """Complete case data with all upstream agent outputs for plea/trial testing.

    Extends make_sample_case_state() with plea offer and attorney assessments.
    """
    data = make_sample_case_state()
    data["plea_offer"] = make_sample_plea_offer()
    data["attorney_assessments"] = make_sample_attorney_assessments()
    return data


# ---------------------------------------------------------------------------
# Mock LLM responses — Motion Drafter
# ---------------------------------------------------------------------------

SAMPLE_LLM_SUPPRESS_RESPONSE: dict[str, Any] = {
    "motions": [
        {
            "id": "motion_001",
            "type": "SUPPRESS",
            "title": "Motion to Suppress Physical Evidence",
            "draft": (
                "DRAFT — ATTORNEY REVIEW REQUIRED\n\n"
                "IN THE STATE COURT OF FULTON COUNTY\n"
                "STATE OF GEORGIA\n\n"
                "STATE OF GEORGIA v. JOHN DOE\n\n"
                "MOTION TO SUPPRESS PHYSICAL EVIDENCE\n\n"
                "COMES NOW the Defendant, John Doe, by and through undersigned "
                "counsel, and moves this Honorable Court to suppress the physical "
                "evidence seized during the warrantless stop and search on the "
                "grounds that said stop violated Defendant's rights under the "
                "Fourth Amendment to the United States Constitution and Article I, "
                "Section I, Paragraph XIII of the Georgia Constitution.\n\n"
                "STATEMENT OF FACTS\n\n"
                "On or about the date in question, Defendant was standing on a "
                "public sidewalk when he was approached and detained by Officer "
                "without reasonable articulable suspicion of criminal activity. "
                "During this unlawful detention, Officer conducted a search of "
                "Defendant's person and seized approximately 2.3 grams of a "
                "substance later identified as cocaine.\n\n"
                "ARGUMENT\n\n"
                "The Fourth Amendment requires that a law enforcement officer have "
                "reasonable articulable suspicion before conducting a Terry stop. "
                "Terry v. Ohio, 392 U.S. 1 (1968) [VERIFIED]. Under Georgia law, "
                "O.C.G.A. § 17-5-30 [VERIFIED] codifies this protection.\n\n"
                "Here, Defendant was engaged in no criminal activity and was merely "
                "standing on a public sidewalk. The officer has articulated no basis "
                "for the initial stop. See State v. Sample, 300 Ga. 123 (2022) "
                "[UNVERIFIED] (suppression granted where officer lacked RAS).\n\n"
                "WHEREFORE, Defendant respectfully requests that this Court grant "
                "this Motion and suppress all physical evidence obtained as a result "
                "of the unlawful stop and search."
            ),
            "status": "DRAFT",
            "filing_deadline": "2024-03-01",
            "supporting_authority": [
                "Terry v. Ohio, 392 U.S. 1 (1968) [VERIFIED]",
                "O.C.G.A. § 17-5-30 [VERIFIED]",
                "State v. Sample, 300 Ga. 123 (2022) [UNVERIFIED]",
            ],
        }
    ],
}

SAMPLE_LLM_DISCOVERY_RESPONSE: dict[str, Any] = {
    "motions": [
        {
            "id": "motion_002",
            "type": "DISCOVERY",
            "title": "Motion for Discovery and Inspection",
            "draft": (
                "DRAFT — ATTORNEY REVIEW REQUIRED\n\n"
                "IN THE STATE COURT OF FULTON COUNTY\n"
                "STATE OF GEORGIA\n\n"
                "STATE OF GEORGIA v. JOHN DOE\n\n"
                "MOTION FOR DISCOVERY AND INSPECTION\n\n"
                "COMES NOW the Defendant, John Doe, and pursuant to O.C.G.A. "
                "§ 17-16-1 et seq. [VERIFIED], moves this Court to order the "
                "State to produce for inspection and copying the following:\n\n"
                "1. All body camera footage from the arresting officer(s)\n"
                "2. All police reports and supplemental reports\n"
                "3. Chain of custody documentation for all seized evidence\n"
                "4. Laboratory analysis reports for the seized substance\n"
                "5. Any and all exculpatory evidence pursuant to Brady v. "
                "Maryland, 373 U.S. 83 (1963) [VERIFIED]\n\n"
                "WHEREFORE, Defendant respectfully requests this Court grant "
                "this Motion and order the State to comply within 10 days."
            ),
            "status": "DRAFT",
            "filing_deadline": "2024-03-15",
            "supporting_authority": [
                "O.C.G.A. § 17-16-1 et seq. [VERIFIED]",
                "Brady v. Maryland, 373 U.S. 83 (1963) [VERIFIED]",
            ],
        }
    ],
}

SAMPLE_LLM_BAIL_RESPONSE: dict[str, Any] = {
    "motions": [
        {
            "id": "motion_003",
            "type": "BAIL_REDUCTION",
            "title": "Motion for Reduction of Bond",
            "draft": (
                "DRAFT — ATTORNEY REVIEW REQUIRED\n\n"
                "IN THE STATE COURT OF FULTON COUNTY\n"
                "STATE OF GEORGIA\n\n"
                "STATE OF GEORGIA v. JOHN DOE\n\n"
                "MOTION FOR REDUCTION OF BOND\n\n"
                "COMES NOW the Defendant, John Doe, and moves this Honorable "
                "Court to reduce Defendant's bond based on the following:\n\n"
                "1. Defendant is a first-time offender with no prior criminal record\n"
                "2. Defendant is employed full-time as a warehouse worker\n"
                "3. Defendant has one dependent child\n"
                "4. Defendant has stable housing in the community\n"
                "5. Defendant is a United States Citizen with strong community ties\n"
                "6. The charged offense is non-violent\n\n"
                "Pursuant to O.C.G.A. § 17-6-1 [VERIFIED], this Court should "
                "consider the Defendant's ties to the community, financial "
                "resources, and the nature of the offense in setting bond.\n\n"
                "WHEREFORE, Defendant respectfully requests that this Court "
                "reduce the current bond to a reasonable amount or release "
                "Defendant on his own recognizance."
            ),
            "status": "DRAFT",
            "filing_deadline": None,
            "supporting_authority": [
                "O.C.G.A. § 17-6-1 [VERIFIED]",
            ],
        }
    ],
}


# ---------------------------------------------------------------------------
# Mock LLM responses — Plea / Trial Analyst
# ---------------------------------------------------------------------------

SAMPLE_LLM_PLEA_TRIAL_RESPONSE: dict[str, Any] = {
    "plea_scenario": {
        "offer_description": (
            "Plea to misdemeanor possession under O.C.G.A. § 16-13-30(a). "
            "12 months probation, $500 fine, substance abuse evaluation, "
            "40 hours community service."
        ),
        "plea_charge": "Misdemeanor possession of a controlled substance",
        "plea_charge_statute": "O.C.G.A. § 16-13-30(a)",
        "original_charges": [
            "Felony possession of a controlled substance — O.C.G.A. § 16-13-30(a)"
        ],
        "sentences": {
            "label": "Plea to misdemeanor possession",
            "probability": 1.0,
            "probability_reasoning": "This is the offered deal — certainty if accepted",
            "incarceration_months": 0,
            "probation_months": 12,
            "fine_amount": 500.0,
            "community_service_hours": 40,
            "treatment_program": True,
            "criminal_record_impact": (
                "Misdemeanor conviction; eligible for First Offender treatment "
                "under O.C.G.A. § 42-8-60 [VERIFIED] which may result in no "
                "conviction on record upon completion"
            ),
            "collateral_consequences": [
                "Possible employment background check impact (misdemeanor)",
                "No immigration consequences (US Citizen)",
            ],
            "notes": [
                "First Offender treatment would avoid a conviction on record",
                "Substance abuse evaluation required regardless",
            ],
        },
        "collateral_consequences_detail": [
            {
                "category": "employment",
                "description": (
                    "Misdemeanor drug conviction may appear on background checks "
                    "but is less severe than felony"
                ),
                "severity": "MEDIUM",
            },
            {
                "category": "housing",
                "description": "May affect public housing eligibility",
                "severity": "LOW",
            },
        ],
        "diversion_eligible": True,
        "diversion_details": (
            "First Offender treatment under O.C.G.A. § 42-8-60 [VERIFIED] — "
            "defendant has no prior felony record and may qualify. Upon successful "
            "completion, the charge is discharged without adjudication of guilt."
        ),
        "expungement_eligible": True,
        "expungement_details": (
            "If First Offender treatment is completed successfully, defendant "
            "may petition for record restriction under O.C.G.A. § 35-3-37 [VERIFIED]."
        ),
    },
    "trial_scenario": {
        "outcomes": [
            {
                "label": "Acquittal at trial",
                "probability": 0.30,
                "probability_reasoning": (
                    "Viable suppression motion (0.75 confidence) targeting the "
                    "initial stop. If suppressed, prosecution loses key physical "
                    "evidence. Attorney estimates 0.35 acquittal probability. "
                    "State v. Sample, 300 Ga. 123 (2022) [UNVERIFIED] supports "
                    "suppression argument."
                ),
                "incarceration_months": 0,
                "probation_months": 0,
                "fine_amount": 0,
                "community_service_hours": 0,
                "treatment_program": False,
                "criminal_record_impact": "No conviction — record clean",
                "collateral_consequences": [],
                "notes": ["Best outcome — no record, no consequences"],
            },
            {
                "label": "Conviction on felony possession (top charge)",
                "probability": 0.45,
                "probability_reasoning": (
                    "If suppression denied and evidence admitted, prosecution "
                    "has strong case: officer testimony + field test + 2.3g cocaine. "
                    "Trial penalty likely applies."
                ),
                "incarceration_months": 24,
                "probation_months": 36,
                "fine_amount": 3000.0,
                "community_service_hours": 0,
                "treatment_program": True,
                "criminal_record_impact": "Felony conviction on record",
                "collateral_consequences": [
                    "Felony on record — significant employment barriers",
                    "May lose public housing eligibility",
                    "Firearm rights restricted under federal law",
                ],
                "notes": [
                    "Trial penalty: post-trial sentence typically 2-3x plea offer",
                    "First Offender treatment may still be available at sentencing",
                ],
            },
            {
                "label": "Conviction on lesser included (misdemeanor possession)",
                "probability": 0.25,
                "probability_reasoning": (
                    "Jury may convict on lesser included if evidence of possession "
                    "is established but jury is sympathetic to quantity argument "
                    "(2.3g is near the misdemeanor threshold)."
                ),
                "incarceration_months": 6,
                "probation_months": 12,
                "fine_amount": 1000.0,
                "community_service_hours": 40,
                "treatment_program": True,
                "criminal_record_impact": "Misdemeanor conviction on record",
                "collateral_consequences": [
                    "Misdemeanor on record — moderate employment impact",
                ],
                "notes": [
                    "Similar record impact to plea but with incarceration time served"
                ],
            },
        ],
        "expected_incarceration_months": 12.3,
        "expected_probation_months": 19.2,
        "trial_penalty_estimate": (
            "Moderate trial penalty expected. Post-trial felony conviction "
            "likely to result in 2-3 years incarceration vs. 0 under plea. "
            "Judge has MODERATE sentencing tendency per attorney assessment."
        ),
        "key_strengths": [
            "Viable suppression motion — officer may have lacked RAS for initial stop",
            "No prior record — jury may be sympathetic",
            "Small quantity (2.3g) — near misdemeanor threshold",
            "Brady material (body cam) may support defense narrative",
        ],
        "key_weaknesses": [
            "Physical evidence (cocaine) is strong if not suppressed",
            "Two officer witnesses — consistent testimony expected",
            "Field test confirmed substance as cocaine",
            "Trial penalty risk if convicted on top charge",
        ],
        "suppression_motion_impact": (
            "HIGH IMPACT: The suppression motion targets the initial stop. "
            "If granted, the physical evidence (cocaine) is excluded and "
            "prosecution's case collapses — acquittal probability rises to ~0.80+. "
            "If denied, trial proceeds on full evidence with acquittal "
            "probability dropping to ~0.15."
        ),
        "jury_considerations": [
            "Fulton County — urban jury pool, generally moderate on drug offenses",
            "Simple possession cases may generate jury sympathy for first offender",
        ],
    },
    "comparison_matrix": {
        "dimensions": [
            {
                "factor": "Maximum incarceration exposure",
                "plea_value": "0 months (probation only)",
                "trial_value": "Up to 24 months if convicted on top charge",
                "advantage": "PLEA",
            },
            {
                "factor": "Expected incarceration (probability-weighted)",
                "plea_value": "0 months",
                "trial_value": "12.3 months",
                "advantage": "PLEA",
            },
            {
                "factor": "Criminal record impact",
                "plea_value": "Misdemeanor (or none with First Offender)",
                "trial_value": "30% chance no record; 45% felony; 25% misdemeanor",
                "advantage": "NEUTRAL",
            },
            {
                "factor": "Collateral consequences",
                "plea_value": "Moderate — misdemeanor drug conviction",
                "trial_value": "Range: none (acquittal) to severe (felony conviction)",
                "advantage": "NEUTRAL",
            },
            {
                "factor": "Financial cost",
                "plea_value": "$500 fine + probation fees",
                "trial_value": "$0–$3,000 fine + trial costs",
                "advantage": "PLEA",
            },
            {
                "factor": "Time to resolution",
                "plea_value": "Immediate — can resolve at next hearing",
                "trial_value": "3–6 months to trial date",
                "advantage": "PLEA",
            },
            {
                "factor": "Certainty of outcome",
                "plea_value": "100% certain — known terms",
                "trial_value": "Uncertain — three possible outcomes",
                "advantage": "PLEA",
            },
            {
                "factor": "Best possible outcome",
                "plea_value": "Misdemeanor or no record with First Offender",
                "trial_value": "Full acquittal — no record, no consequences",
                "advantage": "TRIAL",
            },
            {
                "factor": "Suppression motion leverage",
                "plea_value": "Foregone if plea accepted before ruling",
                "trial_value": "75% viable — may exclude key evidence",
                "advantage": "TRIAL",
            },
            {
                "factor": "Firearm rights",
                "plea_value": "Preserved (misdemeanor)",
                "trial_value": "At risk if convicted on felony charge",
                "advantage": "PLEA",
            },
        ],
    },
    "risk_factors": [
        {
            "factor": "Suppression motion viability",
            "description": (
                "Motion to suppress has 75% viability. If granted, "
                "prosecution's case collapses. This is the single largest "
                "factor favoring trial."
            ),
            "favors": "TRIAL",
            "weight": "HIGH",
            "source": "rights_violation_analysis",
        },
        {
            "factor": "Trial penalty",
            "description": (
                "If convicted at trial on the top charge, sentence will "
                "likely be 2-3x the plea offer. Judge has moderate "
                "sentencing tendency."
            ),
            "favors": "PLEA",
            "weight": "HIGH",
            "source": "attorney_assessments",
        },
        {
            "factor": "First Offender eligibility",
            "description": (
                "Defendant has no prior record and qualifies for First "
                "Offender treatment under O.C.G.A. § 42-8-60, which "
                "would avoid a conviction on record."
            ),
            "favors": "PLEA",
            "weight": "MEDIUM",
            "source": "intake_summary",
        },
        {
            "factor": "Brady material pending",
            "description": (
                "Body camera footage has been requested but not yet "
                "disclosed. This footage may support or undermine "
                "the suppression argument."
            ),
            "favors": "NEUTRAL",
            "weight": "MEDIUM",
            "source": "brady_analysis",
        },
        {
            "factor": "Evidence strength if not suppressed",
            "description": (
                "Physical evidence (2.3g cocaine) + two officer witnesses "
                "make a strong prosecution case if suppression is denied."
            ),
            "favors": "PLEA",
            "weight": "HIGH",
            "source": "legal_research",
        },
        {
            "factor": "Defendant personal circumstances",
            "description": (
                "Employed full-time with one dependent. Incarceration "
                "would have significant personal impact."
            ),
            "favors": "PLEA",
            "weight": "MEDIUM",
            "source": "intake_summary",
        },
    ],
    "flags": ["DECISION_SUPPORT_ONLY", "FIRST_OFFENDER_ELIGIBLE"],
    "confidence_reasoning": (
        "Analysis based on complete charge data, rights violation analysis, "
        "intake summary, legal research, draft motions, and Brady analysis. "
        "Attorney subjective inputs provided. One citation unverified."
    ),
}


SAMPLE_LLM_PLEA_TRIAL_NO_OFFER_RESPONSE: dict[str, Any] = {
    "plea_scenario": {
        "offer_description": "No plea offer provided",
        "plea_charge": "",
        "plea_charge_statute": "",
        "original_charges": [
            "Felony possession of a controlled substance — O.C.G.A. § 16-13-30(a)"
        ],
        "sentences": {
            "label": "N/A — no plea offer",
            "probability": 0.0,
            "probability_reasoning": "No plea offer available for analysis",
            "incarceration_months": 0,
            "probation_months": 0,
            "fine_amount": 0,
            "criminal_record_impact": "N/A",
        },
        "collateral_consequences_detail": [],
        "diversion_eligible": False,
        "diversion_details": "",
        "expungement_eligible": False,
        "expungement_details": "",
    },
    "trial_scenario": {
        "outcomes": [
            {
                "label": "Acquittal at trial",
                "probability": 0.30,
                "probability_reasoning": "Suppression motion viable; officer lacked RAS",
                "incarceration_months": 0,
                "probation_months": 0,
                "fine_amount": 0,
                "community_service_hours": 0,
                "treatment_program": False,
                "criminal_record_impact": "No conviction",
                "collateral_consequences": [],
                "notes": [],
            },
            {
                "label": "Conviction on top charge",
                "probability": 0.45,
                "probability_reasoning": "Strong physical evidence if not suppressed",
                "incarceration_months": 24,
                "probation_months": 36,
                "fine_amount": 3000.0,
                "community_service_hours": 0,
                "treatment_program": True,
                "criminal_record_impact": "Felony conviction",
                "collateral_consequences": [
                    "Felony record — employment barriers",
                    "Firearm rights restricted",
                ],
                "notes": [],
            },
            {
                "label": "Lesser included — misdemeanor possession",
                "probability": 0.25,
                "probability_reasoning": "Jury sympathy possible given small quantity",
                "incarceration_months": 6,
                "probation_months": 12,
                "fine_amount": 1000.0,
                "community_service_hours": 40,
                "treatment_program": True,
                "criminal_record_impact": "Misdemeanor conviction",
                "collateral_consequences": ["Misdemeanor on record"],
                "notes": [],
            },
        ],
        "expected_incarceration_months": 12.3,
        "expected_probation_months": 19.2,
        "trial_penalty_estimate": "Moderate — post-trial sentences typically harsher",
        "key_strengths": [
            "Viable suppression motion",
            "No prior record",
            "Small quantity near misdemeanor threshold",
        ],
        "key_weaknesses": [
            "Strong physical evidence if not suppressed",
            "Two officer witnesses",
        ],
        "suppression_motion_impact": "High impact — case may collapse if evidence suppressed",
        "jury_considerations": ["Fulton County urban jury pool"],
    },
    "comparison_matrix": {
        "dimensions": [],
    },
    "risk_factors": [
        {
            "factor": "No plea offer available",
            "description": "Cannot compare plea vs. trial without an offer from the State",
            "favors": "NEUTRAL",
            "weight": "HIGH",
            "source": "case_data",
        }
    ],
    "flags": ["DECISION_SUPPORT_ONLY", "MISSING_PLEA_OFFER"],
    "confidence_reasoning": "Limited analysis — no plea offer available for comparison.",
}
