"""Template for Motion in Limine — Georgia practice."""

LIMINE_TEMPLATE: dict = {
    "motion_type": "motion_in_limine",
    "title_template": "DEFENDANT'S MOTION IN LIMINE TO EXCLUDE {evidence_description}",
    "sections": [
        {
            "heading": "INTRODUCTION",
            "instructions": (
                "Identify the specific evidence the defendant seeks to exclude "
                "and the rule or constitutional basis. 2-3 sentences."
            ),
        },
        {
            "heading": "STATEMENT OF FACTS",
            "instructions": (
                "Describe the evidence at issue and the context in which the "
                "State is expected to introduce it. Reference the charging "
                "documents and discovery materials."
            ),
        },
        {
            "heading": "ARGUMENT",
            "subsections": [
                {
                    "heading": ("I. THE EVIDENCE SHOULD BE EXCLUDED UNDER O.C.G.A. " "§ 24-4-403"),
                    "instructions": (
                        "Argue that the probative value of the evidence is "
                        "substantially outweighed by the danger of unfair "
                        "prejudice, confusion of the issues, misleading the jury, "
                        "or needless cumulation. Cite Georgia Rule 403 equivalent."
                    ),
                },
                {
                    "heading": "II. ALTERNATIVE GROUNDS FOR EXCLUSION",
                    "instructions": (
                        "Address any additional exclusionary rules: character "
                        "evidence (O.C.G.A. § 24-4-404), hearsay (O.C.G.A. "
                        "§ 24-8-801 et seq.), prior bad acts, or other "
                        "evidentiary rules that support exclusion."
                    ),
                },
                {
                    "heading": "III. PREJUDICE ABSENT EXCLUSION",
                    "instructions": (
                        "Explain how admission would unfairly prejudice the "
                        "defendant's right to a fair trial. Address the specific "
                        "harm the evidence would cause."
                    ),
                },
            ],
        },
        {
            "heading": "CONCLUSION AND PRAYER FOR RELIEF",
            "instructions": (
                "Request a pretrial ruling excluding the specific evidence. "
                "Request a limiting instruction if full exclusion is not granted."
            ),
        },
    ],
    "required_inputs": [
        "charges",
        "legal_research.case_law",
        "intake.client_account",
    ],
    "georgia_specific_notes": [
        (
            "O.C.G.A. § 24-4-403: Exclusion of relevant evidence on grounds of "
            "prejudice, confusion, or waste of time — Georgia's Rule 403 equivalent."
        ),
        (
            "O.C.G.A. § 24-4-404: Character evidence not admissible to prove "
            "conduct, with exceptions for pertinent character traits and "
            "other acts evidence."
        ),
        (
            "O.C.G.A. § 24-4-404(b): Evidence of other crimes, wrongs, or acts "
            "admissible for limited purposes (motive, intent, plan, etc.) but "
            "State must give reasonable pretrial notice."
        ),
        "O.C.G.A. § 24-8-801 et seq.: Hearsay definitions and exceptions.",
        (
            "O.C.G.A. § 24-8-807: Residual hearsay exception — Georgia "
            "equivalent of federal Rule 807."
        ),
        (
            "Motion in limine should be filed sufficiently before trial — "
            "check local Superior Court rules for specific deadlines."
        ),
    ],
}
