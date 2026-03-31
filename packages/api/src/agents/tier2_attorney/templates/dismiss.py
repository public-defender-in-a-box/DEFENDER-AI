"""Template for Motion to Dismiss — Georgia practice."""

DISMISS_TEMPLATE: dict = {
    "motion_type": "motion_to_dismiss",
    "title_template": "DEFENDANT'S MOTION TO DISMISS {basis}",
    "sections": [
        {
            "heading": "INTRODUCTION",
            "instructions": (
                "Identify the charge(s) to be dismissed and the legal basis. " "2-3 sentences."
            ),
        },
        {
            "heading": "STATEMENT OF FACTS",
            "instructions": (
                "Chronological factual narrative supporting dismissal. Include "
                "procedural history, dates of arrest, arraignment, and any "
                "continuances relevant to speedy trial or limitations analysis."
            ),
        },
        {
            "heading": "ARGUMENT",
            "subsections": [
                {
                    "heading": "I. LEGAL STANDARD FOR DISMISSAL",
                    "instructions": (
                        "Set forth the applicable standard — speedy trial demand "
                        "under O.C.G.A. § 17-7-170, statute of limitations under "
                        "O.C.G.A. § 17-3-1 or -2, charging deficiency, or due "
                        "process grounds. Cite controlling Georgia authority."
                    ),
                },
                {
                    "heading": "II. APPLICATION TO THE FACTS",
                    "instructions": (
                        "Apply the legal standard to the case facts. For speedy "
                        "trial: Barker v. Wingo factors as adopted by Georgia "
                        "courts — length of delay, reason for delay, defendant's "
                        "assertion of the right, and prejudice. For limitations: "
                        "calculate the period and show it has run."
                    ),
                },
                {
                    "heading": "III. PREJUDICE TO THE DEFENDANT",
                    "instructions": (
                        "Demonstrate actual or presumed prejudice if applicable. "
                        "Address how continued prosecution harms the defendant."
                    ),
                },
            ],
        },
        {
            "heading": "CONCLUSION AND PRAYER FOR RELIEF",
            "instructions": (
                "Request dismissal of specific charge(s) with or without "
                "prejudice. State the specific relief clearly."
            ),
        },
    ],
    "required_inputs": [
        "charges",
        "legal_research.statutes",
        "legal_research.case_law",
    ],
    "georgia_specific_notes": [
        (
            "O.C.G.A. § 17-7-170: Demand for speedy trial — if demand filed and "
            "State fails to try defendant by end of next succeeding term, case "
            "must be dismissed."
        ),
        "O.C.G.A. § 17-3-1: Statute of limitations for felonies (generally 4 years).",
        "O.C.G.A. § 17-3-2: Statute of limitations for misdemeanors (2 years).",
        (
            "Barker v. Wingo, 407 U.S. 514 (1972) — four-factor balancing test for "
            "Sixth Amendment speedy trial claims, adopted by Georgia courts."
        ),
        (
            "Ruffin v. State — Georgia Court of Appeals: demand for trial must be "
            "filed at the term of arraignment or the next succeeding regular term."
        ),
    ],
}
