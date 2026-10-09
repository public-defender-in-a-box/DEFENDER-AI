"""Template for Motion for Bail Reduction — Georgia practice."""

BAIL_REDUCTION_TEMPLATE: dict = {
    "motion_type": "motion_for_bail_reduction",
    "title_template": "DEFENDANT'S MOTION FOR REDUCTION OF BAIL",
    "sections": [
        {
            "heading": "INTRODUCTION",
            "instructions": (
                "Brief statement identifying the defendant, current bail amount, "
                "and the relief sought. 2-3 sentences."
            ),
        },
        {
            "heading": "STATEMENT OF FACTS",
            "instructions": (
                "Background on arrest and current charges. Include facts relevant "
                "to bail factors: ties to community, employment, family, prior "
                "record, and nature of current charge."
            ),
        },
        {
            "heading": "ARGUMENT",
            "subsections": [
                {
                    "heading": ("I. THE CURRENT BAIL IS EXCESSIVE UNDER O.C.G.A. § 17-6-1"),
                    "instructions": (
                        "Apply the statutory factors from O.C.G.A. § 17-6-1 and the "
                        "Ayala factors. Address each: (1) ability to pay; (2) nature "
                        "of the offense; (3) defendant's ties to the community; "
                        "(4) prior criminal record; (5) history of court appearances; "
                        "(6) risk of flight; (7) danger to community."
                    ),
                },
                {
                    "heading": ("II. PERSONAL CIRCUMSTANCES SUPPORT REDUCED BAIL"),
                    "instructions": (
                        "Argue personal circumstances — employment, family "
                        "obligations, health — support release or reduced bail. "
                        "Reference personal circumstances data from intake."
                    ),
                },
                {
                    "heading": (
                        "III. CONDITIONS OF RELEASE CAN ADEQUATELY PROTECT " "THE COMMUNITY"
                    ),
                    "instructions": (
                        "Propose specific alternative conditions (GPS monitoring, "
                        "check-ins, travel restrictions) that address any flight "
                        "risk or community safety concerns."
                    ),
                },
            ],
        },
        {
            "heading": "CONCLUSION AND PRAYER FOR RELIEF",
            "instructions": (
                "Request specific bail amount or release on recognizance with "
                "conditions. State the specific relief clearly."
            ),
        },
    ],
    "required_inputs": [
        "charges",
        "intake.personal_circumstances",
        "intake.client_account",
    ],
    "georgia_specific_notes": [
        "O.C.G.A. § 17-6-1: Bail in non-capital cases — lists factors courts consider.",
        (
            "Ayala v. State — Georgia courts consider: ties to community, employment, "
            "prior record, severity of charges, and risk of flight."
        ),
        "Georgia Uniform Superior Court Rules govern bail hearing procedures.",
        "O.C.G.A. § 17-6-12: Court may set conditions of release.",
        (
            "For misdemeanors, defendant is generally entitled to bail as a matter "
            "of right under O.C.G.A. § 17-6-1(a)."
        ),
    ],
}
