"""Template for Discovery / Brady Demand — Georgia practice."""

DISCOVERY_BRADY_TEMPLATE: dict = {
    "motion_type": "discovery_brady_demand",
    "title_template": "DEFENDANT'S DEMAND FOR DISCOVERY AND BRADY MATERIAL",
    "sections": [
        {
            "heading": "INTRODUCTION",
            "instructions": (
                "State that the defendant demands discovery pursuant to the "
                "Georgia Criminal Discovery Act and all material required under "
                "Brady v. Maryland. 2-3 sentences."
            ),
        },
        {
            "heading": "LEGAL AUTHORITY",
            "instructions": (
                "Cite Brady v. Maryland, Giglio v. United States, O.C.G.A. "
                "§ 17-16-1 et seq., and Uniform Superior Court Rule 31.1 as "
                "the bases for the demand."
            ),
        },
        {
            "heading": "SPECIFIC DEMANDS",
            "subsections": [
                {
                    "heading": "I. STATUTORY DISCOVERY UNDER O.C.G.A. § 17-16-4",
                    "instructions": (
                        "Demand all statements of co-defendants and witnesses, "
                        "all scientific and forensic reports, documents and "
                        "tangible objects, and witness lists as required by the "
                        "Georgia Criminal Discovery Act."
                    ),
                },
                {
                    "heading": "II. BRADY/GIGLIO MATERIAL",
                    "instructions": (
                        "Demand all exculpatory and impeachment material including: "
                        "evidence favorable to the defense, evidence tending to "
                        "impeach prosecution witnesses, prior inconsistent statements, "
                        "deals or promises to witnesses, disciplinary records of "
                        "officers involved."
                    ),
                },
                {
                    "heading": "III. SPECIFIC ITEMS REQUESTED",
                    "instructions": (
                        "List specific items identified by the Brady Agent as "
                        "missing or potentially exculpatory. Include body camera "
                        "footage, 911 calls, lab reports, officer disciplinary "
                        "records, and any items flagged in the brady_analysis."
                    ),
                },
            ],
        },
        {
            "heading": "CONCLUSION AND PRAYER FOR RELIEF",
            "instructions": (
                "Request the court order the State to produce all demanded "
                "material within a specific timeframe. Request sanctions for "
                "non-compliance if appropriate."
            ),
        },
    ],
    "required_inputs": [
        "charges",
        "brady_analysis",
    ],
    "georgia_specific_notes": [
        "Brady v. Maryland, 373 U.S. 83 (1963) — prosecution must disclose exculpatory evidence.",
        "Giglio v. United States, 405 U.S. 150 (1972) — extends Brady to impeachment material.",
        (
            "O.C.G.A. § 17-16-1 et seq.: Georgia Criminal Discovery Act — governs "
            "discovery obligations in criminal cases."
        ),
        "O.C.G.A. § 17-16-4: Disclosure by the prosecuting attorney.",
        "O.C.G.A. § 17-16-6: Continuing duty to disclose.",
        (
            "Uniform Superior Court Rule 31.1: Requires disclosure of evidence "
            "within the State's possession or control."
        ),
        ("Demand should be filed within 10 days of arraignment per O.C.G.A. " "§ 17-16-2."),
    ],
}
