"""Charge Processing Agent — Tier 1, Step Zero.

First agent activated. Parses charging documents before anything else runs.
Establishes the legal framework for the entire case.

Migrated from standalone charge-processing-agent. Core logic preserved:
- Two-pass extraction (per-document + cross-document analysis)
- Georgia/federal jurisdiction-aware prompts
- Confidence triage with review flagging
- Person deduplication and evidence merging
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.llm_service import call_llm

STATUS = "REAL"

logger = logging.getLogger(__name__)

# Items below this confidence are tagged review_required
_REVIEW_THRESHOLD = 0.5


# ---------------------------------------------------------------------------
# Prompts — preserved from standalone charge-processing-agent
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a legal document analysis AI assisting a public defender's office "
    "in Georgia. You extract structured information from criminal case documents "
    "with precision and thoroughness.\n\n"
    "JURISDICTION KNOWLEDGE:\n"
    "- Georgia State: O.C.G.A. Title 16 (Crimes and Offenses), Title 17 (Criminal Procedure)\n"
    "- Georgia uses accusations for misdemeanors (no grand jury required)\n"
    "- Felonies require grand jury indictment under Georgia Constitution Art. I, \u00a7 I, \u00b6 VIII\n"
    "- Georgia First Offender Act: O.C.G.A. \u00a7 42-8-60\n"
    "- Georgia recidivist statute: O.C.G.A. \u00a7 17-10-7\n"
    "- Court structure: Magistrate Courts (preliminary hearings, warrants), "
    "State Courts (misdemeanors), Superior Courts (felonies)\n"
    "- Federal: Title 18 U.S.C., Federal Rules of Criminal Procedure (Rules 7, 8, 12)\n"
    "- Federal Sentencing Guidelines (USSG)\n"
    "- Federal mandatory minimums (especially 21 U.S.C. \u00a7\u00a7 841, 846 for drug offenses)\n"
    "- Federal conspiracy: 18 U.S.C. \u00a7 371\n"
    "- Relevant conduct under USSG \u00a7 1B1.3\n"
    "- Speedy Trial Act: 18 U.S.C. \u00a7\u00a7 3161-3174\n"
    "- Brady v. Maryland / Giglio v. United States discovery obligations\n\n"
    "EXTRACTION PRINCIPLES:\n"
    "1. Extract EVERY relevant detail \u2014 completeness over speed. "
    "A missed fact is worse than a false positive.\n"
    "2. Assign confidence scores (0.0-1.0) to every extraction:\n"
    "   - 0.9-1.0: Directly stated in clear text\n"
    "   - 0.7-0.89: Strong extraction with minor ambiguity\n"
    "   - 0.5-0.69: Reasonable inference with some uncertainty\n"
    "   - 0.3-0.49: Uncertain, may be incorrect\n"
    "   - 0.0-0.29: Best guess, likely needs correction\n"
    "3. Always include source references (document ID and page number).\n"
    "4. Never make legal judgments \u2014 extract, organize, and flag, "
    "but do not recommend strategy.\n"
    "5. Apply equal analytical rigor to all sources. Do not be more skeptical "
    "of defendant statements than officer statements.\n"
    "6. Actively look for misconduct indicators \u2014 do not just passively note obvious ones.\n"
    "7. Flag uncertainty rather than guessing. A REVIEW_REQUIRED tag is better "
    "than a wrong answer.\n\n"
    "MISCONDUCT DETECTION \u2014 actively look for:\n"
    "- Temporal inconsistencies in police reports (timeline doesn't add up)\n"
    "- Boilerplate language suggesting copy-paste rather than genuine recollection\n"
    "- Consent-to-search language that appears formulaic\n"
    "- Miranda warnings administered after questioning already occurred\n"
    "- Excessive time between arrest and booking\n"
    "- Discrepancies between officer reports and witness accounts\n"
    "- Force descriptions disproportionate to alleged resistance\n"
    "- Search/seizure without articulated probable cause or warrant\n"
    "- Evidence discovered in circumstances suggesting planted evidence\n"
    "- Indications that exculpatory evidence was available but not disclosed\n\n"
    "OUTPUT FORMAT: Always respond with valid JSON matching the requested schema. "
    "Do not include any text outside the JSON object."
)

_EXTRACTION_PROMPT = """Analyze this criminal case document and extract ALL structured information.

Document ID: {document_id}
Document Type: {document_type} (confidence: {doc_type_confidence})
Filename: {filename}

DOCUMENT TEXT:
{document_text}

Extract the following into a single JSON object. For every field that involves interpretation, include a "confidence" score (0.0-1.0) and "source_reference" (page number).

Required JSON structure:
{{
  "defendant": {{
    "name": "string",
    "aliases": ["list"],
    "date_of_birth": "string or null",
    "address": "string or null",
    "prior_record_mentioned": true/false,
    "prior_record_details": "string or null",
    "custody_status": "string or 'unknown'",
    "confidence": 0.0-1.0,
    "source_reference": "page number(s)"
  }},
  "charges": [
    {{
      "count_number": 1,
      "charge_description": "plain language description",
      "statute": {{
        "code": "e.g., O.C.G.A. \u00a7 16-8-2 or 18 U.S.C. \u00a7 922(g)(1)",
        "title": "short title",
        "full_text_reference": "pointer for statute lookup"
      }},
      "degree": "felony/misdemeanor + level",
      "classification": "e.g., Class B Felony",
      "elements": [
        {{
          "element": "what prosecution must prove",
          "factual_support_in_charging_document": "what the document alleges or null",
          "confidence": 0.0-1.0
        }}
      ],
      "penalty_range": {{
        "minimum": "string",
        "maximum": "string",
        "mandatory_minimum": "string or null",
        "notes": "string"
      }},
      "enhancements": [
        {{
          "type": "weapon/prior_record/school_zone/gang/hate_crime/etc.",
          "statute": "string",
          "additional_penalty": "string",
          "factual_basis": "string",
          "confidence": 0.0-1.0,
          "source_reference": "page"
        }}
      ],
      "lesser_included_offenses": ["statutory references"],
      "date_of_alleged_offense": "string or null",
      "location_of_alleged_offense": "string or null",
      "confidence": 0.0-1.0,
      "source_reference": "page"
    }}
  ],
  "factual_allegations": [
    {{
      "allegation_id": "FA-001",
      "summary": "concise plain-language summary",
      "detail": "fuller description with specifics",
      "source_document": "{document_id}",
      "source_page": "page number",
      "category": "criminal_conduct|arrest_circumstances|search_and_seizure|statement_by_defendant|statement_by_witness|physical_evidence|officer_observation",
      "related_charges": [1],
      "exculpatory_potential": false,
      "exculpatory_notes": "why this might help defense, or null",
      "confidence": 0.0-1.0
    }}
  ],
  "persons_of_interest": [
    {{
      "person_id": "PER-001",
      "name": "string",
      "role": "officer|detective|witness|victim|co-defendant|informant|forensic_expert|prosecutor|other",
      "badge_number": "string or null",
      "agency": "string or null",
      "involvement_summary": "string",
      "documents_appearing_in": ["{document_id}"],
      "potential_impeachment_notes": "string or null",
      "confidence": 0.0-1.0
    }}
  ],
  "evidence_items": [
    {{
      "description": "string",
      "type": "physical|documentary|testimonial|digital|forensic",
      "chain_of_custody_notes": "string or null",
      "source_reference": "page",
      "confidence": 0.0-1.0
    }}
  ],
  "misconduct_flags": [
    {{
      "flag_id": "MF-001",
      "category": "police_misconduct|prosecutorial_misconduct|procedural_violation|rights_violation|evidence_handling",
      "subcategory": "excessive_force|unlawful_search|miranda_violation|coerced_confession|chain_of_custody|brady_indicator|fabrication|racial_profiling|etc.",
      "description": "what was detected",
      "factual_basis": "specific facts from the document",
      "legal_significance": "why this matters (e.g., basis for suppression motion)",
      "severity": "high|medium|low",
      "source_document": "{document_id}",
      "source_page": "page",
      "related_charges": [],
      "confidence": 0.0-1.0
    }}
  ],
  "procedural_flags": [
    {{
      "flag_type": "speedy_trial_deadline|preliminary_hearing_required|grand_jury_required|mandatory_appearance|discovery_deadline",
      "description": "string",
      "deadline_date": "string or null",
      "calculated_from": "string or null",
      "statute_reference": "string",
      "confidence": 0.0-1.0
    }}
  ]
}}

IMPORTANT:
- Extract EVERYTHING relevant, even if uncertain (assign low confidence instead of omitting)
- For charges, identify ALL counts including lesser-included offenses
- For misconduct, actively analyze the narrative for red flags
- Include page references for all extractions
- If the document doesn't contain certain categories (e.g., a lab report won't have charges), return empty arrays for those fields"""

_CLASSIFICATION_PROMPT = (
    "You are a legal document classifier for a criminal defense system "
    "operating in Georgia (state and federal courts).\n\n"
    "Given the text of a document, classify it as one of these types:\n"
    "- indictment: A grand jury indictment or superseding indictment\n"
    "- information: A criminal information filed by a prosecutor\n"
    "- accusation: A Georgia misdemeanor accusation\n"
    "- complaint: A criminal complaint or affidavit\n"
    "- arrest_report: An arrest report or booking record\n"
    "- police_report: A police/incident report, supplemental report, or use-of-force report\n"
    "- witness_statement: A statement from a witness or victim\n"
    "- lab_report: A lab report, forensic report, toxicology report\n"
    "- search_warrant: A search warrant application, affidavit, return, or inventory\n"
    "- other: Any other document type\n\n"
    "Respond with ONLY a JSON object in this exact format:\n"
    '{\n  "document_type": "<type>",\n  "confidence": <0.0-1.0>,\n'
    '  "reasoning": "<brief explanation>"\n}'
)

_VALID_DOCUMENT_TYPES = {
    "indictment",
    "information",
    "accusation",
    "complaint",
    "arrest_report",
    "police_report",
    "witness_statement",
    "lab_report",
    "search_warrant",
    "other",
}

_CROSS_DOCUMENT_ANALYSIS_PROMPT = """You are analyzing multiple documents from the same criminal case for a public defender's office in Georgia.

You have been given per-document extractions. Your job is to perform cross-document analysis:

1. INCONSISTENCIES: Identify factual contradictions or discrepancies between documents.
2. MISCONDUCT PATTERNS: Detect patterns across documents that suggest police or prosecutorial misconduct.
3. BRADY INDICATORS: Identify facts suggesting exculpatory evidence that may exist but wasn't disclosed.
4. DIVERSION ELIGIBILITY: Based on the charges and defendant info, assess preliminary eligibility for:
   - Georgia First Offender Act (O.C.G.A. \u00a7 42-8-60)
   - Pretrial diversion (varies by judicial circuit, requires DA approval)
   - Drug court (if drug charges present)
   - Federal pretrial diversion (if federal case)

CASE DATA:
{case_data}

Respond with a JSON object:
{{
  "jurisdiction": {{
    "level": "state|federal|unknown",
    "court": "best determination of the court",
    "confidence": 0.0-1.0
  }},
  "inconsistencies": [
    {{
      "inconsistency_id": "INC-001",
      "description": "what is inconsistent",
      "document_a": {{"document_id": "string", "page": 1, "claim": "what doc A says"}},
      "document_b": {{"document_id": "string", "page": 1, "claim": "what doc B says"}},
      "defense_relevance": "how this helps the defense",
      "severity": "high|medium|low",
      "confidence": 0.0-1.0
    }}
  ],
  "additional_misconduct_flags": [
    {{
      "flag_id": "MF-CROSS-001",
      "category": "police_misconduct|prosecutorial_misconduct|procedural_violation|rights_violation|evidence_handling",
      "subcategory": "string",
      "description": "cross-document pattern detected",
      "factual_basis": "specific facts from multiple documents",
      "legal_significance": "why this matters",
      "severity": "high|medium|low",
      "source_document": "multiple",
      "source_page": "multiple",
      "related_charges": [],
      "confidence": 0.0-1.0
    }}
  ],
  "diversion_eligibility": {{
    "first_offender_act_eligible": {{
      "potentially_eligible": true/false,
      "basis": "reasoning",
      "disqualifying_factors": [],
      "confidence": 0.0-1.0
    }},
    "pretrial_diversion_eligible": {{
      "potentially_eligible": true/false,
      "basis": "reasoning",
      "notes": "string",
      "confidence": 0.0-1.0
    }},
    "drug_court_eligible": {{
      "potentially_eligible": true/false,
      "basis": "reasoning",
      "confidence": 0.0-1.0
    }},
    "federal_pretrial_diversion": {{
      "potentially_eligible": true/false,
      "basis": "reasoning",
      "confidence": 0.0-1.0
    }}
  }},
  "consolidated_defendant": {{
    "name": "best name from all documents",
    "aliases": [],
    "date_of_birth": "string or null",
    "address": "string or null",
    "prior_record_mentioned": true/false,
    "prior_record_details": "string or null",
    "custody_status": "string",
    "confidence": 0.0-1.0,
    "source_reference": "best source"
  }}
}}

IMPORTANT:
- Compare timelines across documents for inconsistencies
- Look for officer statements that conflict with witness statements
- Check if Miranda timing is consistent across documents
- Compare descriptions of the same events from different sources
- Flag any facts that suggest exculpatory evidence should exist"""


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


async def _classify_document(text: str, filename: str) -> dict[str, Any]:
    """Classify document type using LLM. Fallback to 'other' on failure."""
    if not text or len(text.strip()) < 20:
        return {"document_type": "other", "confidence": 0.1, "reasoning": "Insufficient text"}

    sample = text[:4000]
    prompt = f"Filename: {filename}\n\nDocument text (first portion):\n{sample}"

    try:
        result = await call_llm(prompt, system=_CLASSIFICATION_PROMPT, max_tokens=512)
        doc_type = result.get("document_type", "other")
        if doc_type not in _VALID_DOCUMENT_TYPES:
            doc_type = "other"
        return {
            "document_type": doc_type,
            "confidence": min(max(float(result.get("confidence", 0.5)), 0.0), 1.0),
            "reasoning": result.get("reasoning", ""),
        }
    except Exception:
        logger.exception("Classification failed for %s", filename)
        return {"document_type": "other", "confidence": 0.3, "reasoning": "Classification error"}


async def _extract_from_document(
    document_text: str,
    document_id: str,
    document_type: str,
    doc_type_confidence: float,
    filename: str,
) -> dict[str, Any]:
    """Run Pass 1 LLM extraction on a single document."""
    prompt = _EXTRACTION_PROMPT.format(
        document_id=document_id,
        document_type=document_type,
        doc_type_confidence=doc_type_confidence,
        filename=filename,
        document_text=document_text,
    )

    try:
        return await call_llm(prompt, system=_SYSTEM_PROMPT, max_tokens=8192)
    except Exception:
        logger.exception("Extraction failed for %s (%s)", filename, document_id)
        return _empty_extraction(document_id)


async def _run_cross_document_analysis(
    per_document_extractions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run Pass 2 cross-document analysis across all extractions."""
    if not per_document_extractions:
        return _empty_analysis()

    case_data = json.dumps(per_document_extractions, indent=2, default=str)
    if len(case_data) > 100_000:
        case_data = case_data[:100_000] + "\n... [TRUNCATED]"

    prompt = _CROSS_DOCUMENT_ANALYSIS_PROMPT.format(case_data=case_data)

    try:
        return await call_llm(prompt, system=_SYSTEM_PROMPT, max_tokens=8192)
    except Exception:
        logger.exception("Cross-document analysis failed")
        return _empty_analysis()


# ---------------------------------------------------------------------------
# Output assembly helpers
# ---------------------------------------------------------------------------


def _build_case_output(
    matter_id: str,
    documents_info: list[dict[str, Any]],
    per_document_extractions: list[dict[str, Any]],
    cross_analysis: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the final structured case output from all extractions."""
    all_charges: list[dict[str, Any]] = []
    all_allegations: list[dict[str, Any]] = []
    all_persons: list[dict[str, Any]] = []
    all_evidence: list[dict[str, Any]] = []
    all_misconduct: list[dict[str, Any]] = []
    all_procedural: list[dict[str, Any]] = []

    for doc_ext in per_document_extractions:
        extraction = doc_ext.get("extraction", {})
        all_charges.extend(extraction.get("charges", []))
        all_allegations.extend(extraction.get("factual_allegations", []))
        all_persons.extend(extraction.get("persons_of_interest", []))
        all_evidence.extend(extraction.get("evidence_items", []))
        all_misconduct.extend(extraction.get("misconduct_flags", []))
        all_procedural.extend(extraction.get("procedural_flags", []))

    # Cross-analysis misconduct flags
    all_misconduct.extend(cross_analysis.get("additional_misconduct_flags", []))

    # Deduplicate persons by name, keeping highest confidence
    persons_by_name: dict[str, dict[str, Any]] = {}
    for person in all_persons:
        name = person.get("name", "").strip().upper()
        if not name:
            continue
        existing = persons_by_name.get(name)
        if existing is None or person.get("confidence", 0) > existing.get("confidence", 0):
            persons_by_name[name] = person
        else:
            # Merge documents_appearing_in
            existing_docs = set(existing.get("documents_appearing_in", []))
            new_docs = set(person.get("documents_appearing_in", []))
            existing["documents_appearing_in"] = list(existing_docs | new_docs)
    deduplicated_persons = list(persons_by_name.values())

    # Consolidated defendant from cross-analysis or best extraction fallback
    defendant = cross_analysis.get("consolidated_defendant")
    if not defendant or defendant.get("name") == "UNKNOWN":
        for doc_ext in per_document_extractions:
            d = doc_ext.get("extraction", {}).get("defendant", {})
            if d.get("name") and d["name"] != "UNKNOWN":
                defendant = d
                break
    if not defendant:
        defendant = {
            "name": "UNKNOWN",
            "aliases": [],
            "date_of_birth": None,
            "address": None,
            "prior_record_mentioned": False,
            "prior_record_details": None,
            "custody_status": "unknown",
            "confidence": 0.0,
            "source_reference": "",
        }

    return {
        "case_id": matter_id,
        "processing_timestamp": datetime.now(timezone.utc).isoformat(),
        "jurisdiction": cross_analysis.get(
            "jurisdiction",
            {
                "level": "unknown",
                "court": "unknown",
                "confidence": 0.0,
            },
        ),
        "documents_processed": documents_info,
        "defendant": defendant,
        "charges": all_charges,
        "factual_allegations": all_allegations,
        "persons_of_interest": deduplicated_persons,
        "evidence_items": all_evidence,
        "procedural_flags": all_procedural,
        "misconduct_flags": all_misconduct,
        "inconsistencies": cross_analysis.get("inconsistencies", []),
        "diversion_eligibility": cross_analysis.get("diversion_eligibility", {}),
        "processing_metadata": {
            "agent_version": "1.0.0",
            "confidence_summary": {},
            "review_required_count": 0,
        },
    }


def _triage_confidence(case_output: dict[str, Any]) -> dict[str, Any]:
    """Tag items below threshold as review_required and compute distribution."""
    review_count = 0
    buckets = {"very_high": 0, "high": 0, "medium": 0, "low": 0, "very_low": 0}

    def _tag(item: dict[str, Any]) -> None:
        nonlocal review_count
        conf = item.get("confidence", 1.0)
        if isinstance(conf, str):
            try:
                conf = float(conf)
            except (ValueError, TypeError):
                conf = 0.5

        if conf >= 0.9:
            buckets["very_high"] += 1
        elif conf >= 0.7:
            buckets["high"] += 1
        elif conf >= 0.5:
            buckets["medium"] += 1
        elif conf >= 0.3:
            buckets["low"] += 1
        else:
            buckets["very_low"] += 1

        if conf < _REVIEW_THRESHOLD:
            item["review_required"] = True
            review_count += 1

    for charge in case_output.get("charges", []):
        _tag(charge)
        for element in charge.get("elements", []):
            _tag(element)
        for enhancement in charge.get("enhancements", []):
            _tag(enhancement)

    for allegation in case_output.get("factual_allegations", []):
        _tag(allegation)

    for person in case_output.get("persons_of_interest", []):
        _tag(person)

    for flag in case_output.get("misconduct_flags", []):
        _tag(flag)

    for incon in case_output.get("inconsistencies", []):
        _tag(incon)

    for pflag in case_output.get("procedural_flags", []):
        _tag(pflag)

    if "defendant" in case_output:
        _tag(case_output["defendant"])

    meta = case_output.setdefault("processing_metadata", {})
    meta["confidence_summary"] = buckets
    meta["review_required_count"] = review_count

    return case_output


def _compute_overall_confidence(case_output: dict[str, Any]) -> float:
    """Derive a single confidence score from the confidence distribution."""
    buckets = case_output.get("processing_metadata", {}).get("confidence_summary", {})
    weights = {
        "very_high": 0.95,
        "high": 0.8,
        "medium": 0.6,
        "low": 0.4,
        "very_low": 0.15,
    }
    total = sum(buckets.get(k, 0) for k in weights)
    if total == 0:
        return 0.75  # default when no items extracted
    weighted = sum(buckets.get(k, 0) * v for k, v in weights.items())
    return round(weighted / total, 3)


def _empty_extraction(document_id: str) -> dict[str, Any]:
    """Minimal extraction structure when extraction fails."""
    return {
        "defendant": {
            "name": "UNKNOWN",
            "aliases": [],
            "date_of_birth": None,
            "address": None,
            "prior_record_mentioned": False,
            "prior_record_details": None,
            "custody_status": "unknown",
            "confidence": 0.0,
            "source_reference": document_id,
        },
        "charges": [],
        "factual_allegations": [],
        "persons_of_interest": [],
        "evidence_items": [],
        "misconduct_flags": [],
        "procedural_flags": [],
    }


def _empty_analysis() -> dict[str, Any]:
    """Empty cross-document analysis structure when analysis fails."""
    return {
        "jurisdiction": {"level": "unknown", "court": "unknown", "confidence": 0.0},
        "inconsistencies": [],
        "additional_misconduct_flags": [],
        "diversion_eligibility": {
            "first_offender_act_eligible": {
                "potentially_eligible": False,
                "basis": "Insufficient information",
                "disqualifying_factors": [],
                "confidence": 0.0,
            },
            "pretrial_diversion_eligible": {
                "potentially_eligible": False,
                "basis": "Insufficient information",
                "notes": "",
                "confidence": 0.0,
            },
            "drug_court_eligible": {
                "potentially_eligible": False,
                "basis": "Insufficient information",
                "confidence": 0.0,
            },
            "federal_pretrial_diversion": {
                "potentially_eligible": False,
                "basis": "Insufficient information",
                "confidence": 0.0,
            },
        },
        "consolidated_defendant": {
            "name": "UNKNOWN",
            "aliases": [],
            "date_of_birth": None,
            "address": None,
            "prior_record_mentioned": False,
            "prior_record_details": None,
            "custody_status": "unknown",
            "confidence": 0.0,
            "source_reference": "",
        },
    }


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class ChargeProcessingAgent(BaseAgent):
    agent_id = "charge_processing"
    agent_name = "Charge Processing Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Parse charging documents into structured case data.

        Supports single-document (standard pipeline) and multi-document mode.

        Input keys:
            document_text: str — extracted document text
            document_type: str — COMPLAINT, INDICTMENT, etc.
            jurisdiction: str — GA, federal, etc.
            filename: str — original filename (optional)
            matter_id: str — case/matter identifier (optional)
            documents: list[dict] — for multi-document processing (optional)

        Output: ConfidenceRated dict with full case extraction.
        """
        self.log_action(
            "charge_processing_started",
            {
                "document_type": input_data.get("document_type"),
                "jurisdiction": input_data.get("jurisdiction"),
                "text_length": len(input_data.get("document_text", "")),
            },
        )

        matter_id = input_data.get("matter_id", input_data.get("case_id", "unknown"))
        documents_raw = input_data.get("documents")

        # Build list of documents to process
        if documents_raw and isinstance(documents_raw, list):
            docs = []
            for i, doc in enumerate(documents_raw):
                docs.append(
                    {
                        "document_id": doc.get("id", f"doc_{i + 1}"),
                        "filename": doc.get("file_name", f"document_{i + 1}"),
                        "document_text": doc.get("extracted_text", ""),
                        "document_type": doc.get("type", "UNKNOWN"),
                        "doc_type_confidence": doc.get("type_confidence", 0.5),
                    }
                )
        else:
            # Single document mode
            filename = input_data.get("filename", "document_1")
            doc_type = input_data.get("document_type", "UNKNOWN")
            doc_type_confidence = 0.9  # assumed if explicitly provided

            # Classify if type is unknown
            if doc_type in ("UNKNOWN", ""):
                classification = await _classify_document(
                    input_data.get("document_text", ""),
                    filename,
                )
                doc_type = classification["document_type"]
                doc_type_confidence = classification["confidence"]

            docs = [
                {
                    "document_id": "doc_1",
                    "filename": filename,
                    "document_text": input_data.get("document_text", ""),
                    "document_type": doc_type,
                    "doc_type_confidence": doc_type_confidence,
                }
            ]

        # Pass 1 — per-document extraction
        per_document_extractions: list[dict[str, Any]] = []
        documents_info: list[dict[str, Any]] = []

        for doc in docs:
            extraction = await _extract_from_document(
                document_text=doc["document_text"],
                document_id=doc["document_id"],
                document_type=doc["document_type"],
                doc_type_confidence=doc["doc_type_confidence"],
                filename=doc["filename"],
            )
            per_document_extractions.append(
                {
                    "document_id": doc["document_id"],
                    "filename": doc["filename"],
                    "document_type": doc["document_type"],
                    "extraction": extraction,
                }
            )
            documents_info.append(
                {
                    "document_id": doc["document_id"],
                    "filename": doc["filename"],
                    "document_type": doc["document_type"],
                    "document_type_confidence": doc["doc_type_confidence"],
                }
            )

        # Pass 2 — cross-document analysis
        cross_analysis = await _run_cross_document_analysis(per_document_extractions)

        # Assemble and triage
        case_output = _build_case_output(
            matter_id,
            documents_info,
            per_document_extractions,
            cross_analysis,
        )
        case_output = _triage_confidence(case_output)
        overall_confidence = _compute_overall_confidence(case_output)

        self.log_action(
            "charge_processing_completed",
            {
                "charges_count": len(case_output.get("charges", [])),
                "allegations_count": len(case_output.get("factual_allegations", [])),
                "persons_count": len(case_output.get("persons_of_interest", [])),
                "misconduct_count": len(case_output.get("misconduct_flags", [])),
                "overall_confidence": overall_confidence,
            },
        )

        return self.wrap_output(case_output, confidence=overall_confidence)
