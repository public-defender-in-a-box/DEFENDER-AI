"""Realistic sample CaseState for a Georgia misdemeanor drug possession case.

O.C.G.A. § 16-13-30(a) — Possession of a controlled substance.
Includes a 4th Amendment warrantless search rights violation, mixed
citation verification statuses, and fact discrepancies.
"""


def make_sample_case_state() -> dict:
    """Return a fully populated case state dict for testing."""
    return {
        "case_id": "test_case_GA_2024_001",
        "case_number": "24-CR-12345",
        "jurisdiction": "GA",
        "charges": [
            {
                "charge_id": "charge_001",
                "statute_section": "O.C.G.A. § 16-13-30(a)",
                "offense_title": "Possession of a Controlled Substance (Cocaine)",
                "degree": "misdemeanor",
                "elements": [
                    "Knowingly possessed",
                    "A controlled substance (cocaine, Schedule II)",
                    "Less than one ounce",
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
                "procedural_requirements": [
                    "Arraignment within 72 hours of arrest",
                ],
                "factual_allegations": [
                    "Defendant observed near intersection of Peachtree St and Andrew Young International Blvd",
                    "Officer observed defendant discard small plastic bag",
                    "Field test positive for cocaine, approximately 2.3 grams",
                ],
                "officers": ["Officer James Smith, Badge #4521, APD Zone 3"],
                "witnesses": ["Officer Maria Garcia, Badge #3847, APD Zone 3"],
            },
        ],
        "rights_violations": [
            {
                "amendment": "4th",
                "description": "Warrantless search of defendant's person and belongings",
                "basis": (
                    "Officer conducted a pat-down search without reasonable articulable "
                    "suspicion. Defendant was standing on a public sidewalk and had not "
                    "been observed committing any crime prior to the stop. The officer's "
                    "claim that defendant 'discarded' the substance is disputed by the "
                    "client, who states the officer reached into his jacket pocket."
                ),
                "suppression_viability": 0.75,
                "supporting_facts": [
                    "Client states he was waiting for a rideshare when approached",
                    "No dispatch call or tip reported — officer-initiated stop",
                    "Client denies discarding anything",
                    "No body camera footage has been produced",
                ],
                "officer_client_discrepancies": [
                    "Officer says substance was discarded; client says it was taken from pocket during pat-down",
                    "Officer claims defendant was 'acting suspiciously'; client says he was standing still on phone",
                ],
            },
        ],
        "intake_summary": {
            "session_id": "intake_001",
            "completed_at": "2024-02-15T14:30:00Z",
            "completion_percentage": 0.85,
            "client_account": (
                "I was standing on the sidewalk on Peachtree Street waiting for my Uber "
                "around 2:30 AM after leaving a friend's birthday party at a nearby bar. "
                "An officer approached me and asked what I was doing. I told him I was "
                "waiting for a ride. He said I matched a description and told me to put "
                "my hands on the wall. He patted me down and reached into my jacket pocket. "
                "I never threw anything on the ground."
            ),
            "facts": [
                {
                    "id": "fact_001",
                    "category": "ARREST_TIMELINE",
                    "statement": "Arrest occurred at approximately 2:30 AM on January 15, 2024",
                    "confidence": "HIGH",
                },
                {
                    "id": "fact_002",
                    "category": "OFFICER_CONDUCT",
                    "statement": "Officer initiated contact without dispatch call or reported tip",
                    "confidence": "MEDIUM",
                },
                {
                    "id": "fact_003",
                    "category": "EVIDENCE",
                    "statement": "2.3 grams of suspected cocaine recovered",
                    "confidence": "HIGH",
                },
                {
                    "id": "fact_004",
                    "category": "OFFICER_CONDUCT",
                    "statement": "Client reports officer reached into jacket pocket without consent",
                    "confidence": "MEDIUM",
                },
            ],
            "inconsistencies": [
                {
                    "id": "inconsistency_001",
                    "client_statement": "Officer reached into my jacket pocket",
                    "document_statement": "Officer observed defendant discard a small plastic bag",
                    "severity": "CRITICAL",
                    "possible_explanations": [
                        "Client may be minimizing involvement",
                        "Officer may have mischaracterized the search as a discard to justify the seizure",
                    ],
                },
            ],
            "personal_circumstances": {
                "citizenship": "US Citizen",
                "employment_status": "Employed — line cook at local restaurant",
                "housing_status": "Renting apartment",
                "dependents": 0,
                "mental_health_history": None,
                "substance_abuse_history": None,
                "military_service": False,
                "education_status": "High school diploma",
                "prior_record_self_report": "No prior criminal record",
                "custody_status": "IN_CUSTODY",
            },
            "in_custody": True,
        },
        "legal_research": {
            "statutes": [
                {
                    "statute_section": "O.C.G.A. § 16-13-30(a)",
                    "full_text": "It is unlawful for any person to purchase, possess, or have under his or her control any controlled substance.",
                    "elements_breakdown": [
                        "Purchase, possess, or have under control",
                        "Controlled substance",
                    ],
                    "verification_status": "VERIFIED",
                },
                {
                    "statute_section": "O.C.G.A. § 17-5-30",
                    "full_text": "A defendant may move to suppress evidence obtained in violation of the Constitution.",
                    "elements_breakdown": [],
                    "verification_status": "VERIFIED",
                },
            ],
            "case_law": [
                {
                    "case_name": "Terry v. Ohio",
                    "citation": "392 U.S. 1 (1968)",
                    "court": "U.S. Supreme Court",
                    "year": 1968,
                    "holding": "Officers may conduct a brief investigatory stop with reasonable suspicion of criminal activity and a limited frisk for weapons.",
                    "relevance": "Sets the standard for lawful stop and frisk — officer must have reasonable articulable suspicion.",
                    "favorable": True,
                    "factual_similarity": "HIGH",
                    "verification_status": "VERIFIED",
                },
                {
                    "case_name": "State v. Allen",
                    "citation": "No. S23A0001 (Ga. 2023)",
                    "court": "Georgia Supreme Court",
                    "year": 2023,
                    "holding": "Georgia applies the good-faith exception to the exclusionary rule narrowly.",
                    "relevance": "Supports argument that exclusionary rule should apply when officer lacked reasonable suspicion.",
                    "favorable": True,
                    "factual_similarity": "MEDIUM",
                    "verification_status": "UNVERIFIED",
                },
                {
                    "case_name": "Mapp v. Ohio",
                    "citation": "367 U.S. 643 (1961)",
                    "court": "U.S. Supreme Court",
                    "year": 1961,
                    "holding": "Evidence obtained through unconstitutional search and seizure is inadmissible in state court.",
                    "relevance": "Foundation for suppression argument — exclusionary rule applies to state proceedings.",
                    "favorable": True,
                    "factual_similarity": "MEDIUM",
                    "verification_status": "VERIFIED",
                },
            ],
        },
        "brady_analysis": {
            "gaps": [
                {
                    "id": "brady_001",
                    "category": "MISSING_REPORT",
                    "description": "No body camera footage has been produced despite APD body camera policy",
                    "expected_evidence": "Body-worn camera footage from Officer Smith during the stop and search",
                    "basis": "APD General Order 3.4.20 requires body cameras to be activated during all citizen encounters",
                },
            ],
            "giglio_checklist": [
                {
                    "officer": "Officer James Smith, Badge #4521",
                    "disciplinary_record_requested": False,
                    "status": "PENDING",
                },
            ],
            "missing_reports": [
                "Body camera footage from Officer Smith",
                "Body camera footage from Officer Garcia (witness)",
                "Dispatch records (if any)",
            ],
        },
    }


def make_minimal_case_state() -> dict:
    """Return a minimal case state with limited data for testing edge cases."""
    return {
        "case_id": "test_case_GA_2024_002",
        "case_number": "24-CR-99999",
        "jurisdiction": "GA",
        "charges": [
            {
                "charge_id": "charge_002",
                "statute_section": "O.C.G.A. § 16-13-30(a)",
                "offense_title": "Possession of a Controlled Substance",
                "degree": "misdemeanor",
                "elements": ["Knowingly possessed", "A controlled substance"],
                "penalty_range": {},
                "enhancements": [],
                "procedural_requirements": [],
            },
        ],
        "rights_violations": [],
        "intake_summary": {},
        "legal_research": {},
        "brady_analysis": {},
    }


# Pre-built LLM response for mocking — matches the expected JSON schema
SAMPLE_LLM_SUPPRESS_RESPONSE: dict = {
    "title": "DEFENDANT'S MOTION TO SUPPRESS PHYSICAL EVIDENCE",
    "case_caption": "STATE OF GEORGIA v. DEFENDANT, Case No. 24-CR-12345",
    "court": "IN THE STATE COURT OF FULTON COUNTY, STATE OF GEORGIA",
    "sections": [
        {
            "heading": "INTRODUCTION",
            "content": (
                "Defendant respectfully moves this Court to suppress all physical "
                "evidence seized during a warrantless search on January 15, 2024. "
                "The search violated Defendant's rights under the Fourth Amendment "
                "to the United States Constitution and Article I, Section I, "
                "Paragraph XIII of the Georgia Constitution. "
                "DRAFT — ATTORNEY REVIEW REQUIRED"
            ),
            "citations": [
                "U.S. Const. amend. IV [VERIFIED]",
                "Ga. Const. art. I, § I, ¶ XIII [VERIFIED]",
            ],
        },
        {
            "heading": "STATEMENT OF FACTS",
            "content": (
                "On January 15, 2024, at approximately 2:30 AM, Defendant was "
                "standing on the sidewalk on Peachtree Street waiting for a "
                "rideshare vehicle. Officer James Smith of the Atlanta Police "
                "Department approached Defendant without a dispatch call or "
                "reported tip. Officer Smith directed Defendant to place his hands "
                "on a wall and conducted a pat-down search, during which the officer "
                "reached into Defendant's jacket pocket and recovered 2.3 grams of "
                "a substance later identified as cocaine. "
                "[NOTE: Officer account differs — see discrepancy report. Officer "
                "claims defendant discarded the substance, while Defendant states "
                "officer reached into his pocket.]"
            ),
            "citations": [],
        },
        {
            "heading": "ARGUMENT: THE FOURTH AMENDMENT REQUIRES SUPPRESSION",
            "content": (
                "Under Terry v. Ohio, 392 U.S. 1 (1968), an officer may conduct "
                "a brief investigatory stop only when the officer has reasonable "
                "articulable suspicion that criminal activity is afoot. Here, "
                "Officer Smith had no such suspicion. Defendant was merely standing "
                "on a public sidewalk. The officer's generalized claim that Defendant "
                "was 'acting suspiciously' is insufficient. See Terry, 392 U.S. at 21. "
                "Furthermore, under Mapp v. Ohio, 367 U.S. 643 (1961), evidence "
                "obtained through an unconstitutional search is inadmissible. Georgia "
                "follows this rule and applies the good-faith exception narrowly. "
                "See State v. Allen, No. S23A0001 (Ga. 2023). The statutory basis "
                "for suppression is provided by O.C.G.A. § 17-5-30. The fruit of "
                "the poisonous tree doctrine, codified at O.C.G.A. § 24-14-22, "
                "requires exclusion of all derivative evidence."
            ),
            "citations": [
                "Terry v. Ohio, 392 U.S. 1 (1968) [VERIFIED]",
                "Mapp v. Ohio, 367 U.S. 643 (1961) [VERIFIED]",
                "State v. Allen, No. S23A0001 (Ga. 2023) [UNVERIFIED]",
                "O.C.G.A. § 17-5-30 [VERIFIED]",
                "O.C.G.A. § 24-14-22 [VERIFIED]",
            ],
        },
        {
            "heading": "CONCLUSION AND PRAYER FOR RELIEF",
            "content": (
                "For the foregoing reasons, Defendant respectfully requests that "
                "this Court suppress all physical evidence — specifically the 2.3 "
                "grams of suspected cocaine — seized from Defendant's person on "
                "January 15, 2024, and all evidence derived therefrom under the "
                "fruit of the poisonous tree doctrine."
            ),
            "citations": [],
        },
    ],
    "prayer_for_relief": (
        "Defendant prays this Court enter an Order suppressing the 2.3 grams "
        "of suspected cocaine and all derivative evidence, and for such other "
        "and further relief as this Court deems just and proper."
    ),
    "filing_deadline": "10 days after arraignment",
    "filing_deadline_basis": "O.C.G.A. § 17-5-30(b)",
    "flags": [
        "Officer account conflicts with client account on search circumstances",
        "Body camera footage missing — may be critical evidence",
    ],
    "confidence_reasoning": (
        "Moderate-to-high confidence. Strong factual basis from client account, "
        "verified controlling authority (Terry, Mapp), but one key citation "
        "(State v. Allen) is unverified and the critical body camera footage "
        "is missing."
    ),
}


SAMPLE_LLM_DISCOVERY_RESPONSE: dict = {
    "title": "DEFENDANT'S DEMAND FOR DISCOVERY AND BRADY MATERIAL",
    "case_caption": "STATE OF GEORGIA v. DEFENDANT, Case No. 24-CR-12345",
    "court": "IN THE STATE COURT OF FULTON COUNTY, STATE OF GEORGIA",
    "sections": [
        {
            "heading": "INTRODUCTION",
            "content": (
                "Defendant demands discovery of all materials in the State's "
                "possession pursuant to the Georgia Criminal Discovery Act, "
                "O.C.G.A. § 17-16-1 et seq., and all exculpatory and "
                "impeachment material required under Brady v. Maryland and "
                "Giglio v. United States. DRAFT — ATTORNEY REVIEW REQUIRED"
            ),
            "citations": [
                "O.C.G.A. § 17-16-1 et seq. [VERIFIED]",
                "Brady v. Maryland, 373 U.S. 83 (1963) [VERIFIED]",
                "Giglio v. United States, 405 U.S. 150 (1972) [VERIFIED]",
            ],
        },
        {
            "heading": "LEGAL AUTHORITY",
            "content": (
                "The State's duty to disclose arises under both constitutional "
                "and statutory authority. Under Brady v. Maryland, 373 U.S. 83 "
                "(1963), the prosecution must disclose evidence favorable to the "
                "defense. Giglio v. United States, 405 U.S. 150 (1972), extends "
                "this obligation to impeachment material. The Georgia Criminal "
                "Discovery Act, O.C.G.A. § 17-16-4, requires disclosure of "
                "statements, reports, and tangible evidence."
            ),
            "citations": [
                "Brady v. Maryland, 373 U.S. 83 (1963) [VERIFIED]",
                "Giglio v. United States, 405 U.S. 150 (1972) [VERIFIED]",
                "O.C.G.A. § 17-16-4 [VERIFIED]",
            ],
        },
        {
            "heading": "SPECIFIC DEMANDS",
            "content": (
                "Defendant specifically demands: (1) Body-worn camera footage "
                "from Officer James Smith, Badge #4521, during the January 15, "
                "2024 stop and search, per APD General Order 3.4.20; (2) Body-worn "
                "camera footage from Officer Maria Garcia, Badge #3847; "
                "(3) Any dispatch records related to the stop; (4) Disciplinary "
                "records for Officer Smith; (5) All lab reports and chain of "
                "custody documentation for the suspected cocaine; (6) Any prior "
                "inconsistent statements by the officers."
            ),
            "citations": [
                "O.C.G.A. § 17-16-4 [VERIFIED]",
                "Uniform Superior Court Rule 31.1 [VERIFIED]",
            ],
        },
        {
            "heading": "CONCLUSION AND PRAYER FOR RELIEF",
            "content": (
                "Defendant prays this Court order the State to produce all "
                "demanded material within 10 days and impose appropriate "
                "sanctions for any failure to comply."
            ),
            "citations": [],
        },
    ],
    "prayer_for_relief": (
        "Defendant prays this Court order the State to disclose all materials "
        "demanded herein within 10 days and grant such further relief as the "
        "Court deems just."
    ),
    "filing_deadline": "10 days after arraignment",
    "filing_deadline_basis": "O.C.G.A. § 17-16-2",
    "flags": ["Body camera footage missing — critical evidence"],
    "confidence_reasoning": (
        "High confidence. Discovery demand is straightforward and based on "
        "well-established constitutional and statutory authority. Brady analysis "
        "identifies specific missing items."
    ),
}


SAMPLE_LLM_BAIL_RESPONSE: dict = {
    "title": "DEFENDANT'S MOTION FOR REDUCTION OF BAIL",
    "case_caption": "STATE OF GEORGIA v. DEFENDANT, Case No. 24-CR-12345",
    "court": "IN THE STATE COURT OF FULTON COUNTY, STATE OF GEORGIA",
    "sections": [
        {
            "heading": "INTRODUCTION",
            "content": (
                "Defendant respectfully moves this Court for a reduction of bail. "
                "Defendant is currently in custody on a misdemeanor charge of "
                "Possession of a Controlled Substance under O.C.G.A. § 16-13-30(a). "
                "DRAFT — ATTORNEY REVIEW REQUIRED"
            ),
            "citations": ["O.C.G.A. § 16-13-30(a) [VERIFIED]"],
        },
        {
            "heading": "STATEMENT OF FACTS",
            "content": (
                "Defendant is a United States citizen, employed as a line cook, "
                "renting an apartment in the community, with no prior criminal "
                "record. The charge is a misdemeanor involving less than one ounce "
                "of a controlled substance."
            ),
            "citations": [],
        },
        {
            "heading": "ARGUMENT",
            "content": (
                "Under O.C.G.A. § 17-6-1, Defendant is entitled to bail as a "
                "matter of right for this misdemeanor offense. The Ayala factors "
                "favor release: Defendant has strong community ties through "
                "employment and housing, no prior record, and the charge is a "
                "non-violent misdemeanor. Defendant poses no flight risk and no "
                "danger to the community."
            ),
            "citations": [
                "O.C.G.A. § 17-6-1 [VERIFIED]",
                "Ayala v. State [UNVERIFIED]",
            ],
        },
        {
            "heading": "CONCLUSION AND PRAYER FOR RELIEF",
            "content": (
                "Defendant prays this Court reduce bail to personal recognizance "
                "or a reasonable amount with conditions of release."
            ),
            "citations": [],
        },
    ],
    "prayer_for_relief": (
        "Defendant prays this Court reduce bail and release Defendant on "
        "personal recognizance or set bail at a reasonable amount."
    ),
    "filing_deadline": None,
    "filing_deadline_basis": None,
    "flags": [],
    "confidence_reasoning": (
        "High confidence. Misdemeanor bail reduction is straightforward with "
        "strong personal circumstances supporting release."
    ),
}
