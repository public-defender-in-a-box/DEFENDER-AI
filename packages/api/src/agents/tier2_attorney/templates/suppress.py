"""Template for Motion to Suppress — Georgia practice."""

SUPPRESS_TEMPLATE: dict = {
    "motion_type": "motion_to_suppress",
    "title_template": "DEFENDANT'S MOTION TO SUPPRESS {evidence_type}",
    "sections": [
        {
            "heading": "INTRODUCTION",
            "instructions": (
                "Brief statement of what is being suppressed and the constitutional "
                "basis. 2-3 sentences."
            ),
        },
        {
            "heading": "STATEMENT OF FACTS",
            "instructions": (
                "Chronological factual narrative drawn from intake facts and arrest "
                "report. Include all facts relevant to the constitutional violation. "
                "Cite to specific record references where available."
            ),
        },
        {
            "heading": "ARGUMENT",
            "subsections": [
                {
                    "heading": "I. THE {amendment} AMENDMENT REQUIRES SUPPRESSION",
                    "instructions": (
                        "Legal standard from Georgia appellate authority. Apply facts "
                        "to the legal standard. Cite verified case law. Address likely "
                        "state counterarguments."
                    ),
                },
            ],
        },
        {
            "heading": "CONCLUSION AND PRAYER FOR RELIEF",
            "instructions": (
                "Specific relief requested. What evidence should be suppressed, and "
                "what flows from that (fruit of the poisonous tree)."
            ),
        },
    ],
    "required_inputs": [
        "rights_violations",
        "intake.client_account",
        "legal_research.case_law",
        "charges",
    ],
    "georgia_specific_notes": [
        "Georgia follows the federal exclusionary rule: Mapp v. Ohio as incorporated.",
        "State v. Allen (2023) — Georgia applies the good-faith exception narrowly.",
        "O.C.G.A. § 17-5-30: Georgia statutory suppression provision.",
        "O.C.G.A. § 24-14-22: Fruit of the poisonous tree codified in Georgia evidence code.",
        (
            "Motion must be filed within 10 days of arraignment or by the court's "
            "pretrial deadline (O.C.G.A. § 17-5-30(b)) — check local rules."
        ),
    ],
}
