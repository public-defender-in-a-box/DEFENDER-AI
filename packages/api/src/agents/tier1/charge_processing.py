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
from src.models.responses.charge_processing import (
    CrossDocumentAnalysis,
    DocumentClassification,
    DocumentExtraction,
)
from src.prompts import compose_version, load_prompt
from src.services.model_gateway import ModelCallRequest, call_model

STATUS = "REAL"

logger = logging.getLogger(__name__)

# Items below this confidence are tagged review_required
_REVIEW_THRESHOLD = 0.5


# ---------------------------------------------------------------------------
# Prompts — preserved from standalone charge-processing-agent, now versioned files
# under src/prompts/charge_processing/
# ---------------------------------------------------------------------------

_SYSTEM = load_prompt("charge_processing.system", "v1")
_EXTRACT = load_prompt("charge_processing.extract", "v1")
_CLASSIFY = load_prompt("charge_processing.classify", "v1")
_CLASSIFY_INPUT = load_prompt("charge_processing.classify_input", "v1")
_CROSS_DOCUMENT = load_prompt("charge_processing.cross_document", "v1")

# Thinking tokens count toward max_tokens on current models (Phase 1 §2).
_CLASSIFY_MAX_TOKENS = 4000
_EXTRACT_MAX_TOKENS = 16000
_CROSS_DOCUMENT_MAX_TOKENS = 16000


# ---------------------------------------------------------------------------
# Extraction helpers. A failed model call raises (ModelCallError); there is no
# empty-extraction fallback, so a failure can never be merged as a zero-charge
# success (PHASE_1_MODEL_GATEWAY.md §3).
# ---------------------------------------------------------------------------


async def _classify_document(text: str, filename: str) -> dict[str, Any]:
    """Classify document type."""
    if not text or len(text.strip()) < 20:
        return {"document_type": "other", "confidence": 0.1, "rationale": "Insufficient text"}

    result = await call_model(
        ModelCallRequest(
            prompt=_CLASSIFY_INPUT.text.format(filename=filename, sample=text[:4000]),
            system=_CLASSIFY.text,
            max_tokens=_CLASSIFY_MAX_TOKENS,
            response_model=DocumentClassification,
            prompt_id="charge_processing.classify",
            prompt_version=compose_version(_CLASSIFY, _CLASSIFY_INPUT),
            agent_id="charge_processing",
        )
    )
    classification = result.data
    return {
        "document_type": classification.document_type,
        "confidence": min(max(classification.confidence, 0.0), 1.0),
        "rationale": classification.rationale,
    }


async def _extract_from_document(
    document_text: str,
    document_id: str,
    document_type: str,
    doc_type_confidence: float,
    filename: str,
) -> dict[str, Any]:
    """Run Pass 1 extraction on a single document."""
    result = await call_model(
        ModelCallRequest(
            prompt=_EXTRACT.text.format(
                document_id=document_id,
                document_type=document_type,
                doc_type_confidence=doc_type_confidence,
                filename=filename,
                document_text=document_text,
            ),
            system=_SYSTEM.text,
            max_tokens=_EXTRACT_MAX_TOKENS,
            response_model=DocumentExtraction,
            prompt_id="charge_processing.extract",
            prompt_version=compose_version(_SYSTEM, _EXTRACT),
            agent_id="charge_processing",
        )
    )
    return result.data.model_dump()


async def _run_cross_document_analysis(
    per_document_extractions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run Pass 2 cross-document analysis across all extractions."""
    if not per_document_extractions:
        return _empty_analysis()

    case_data = json.dumps(per_document_extractions, indent=2, default=str)
    if len(case_data) > 100_000:
        case_data = case_data[:100_000] + "\n... [TRUNCATED]"

    result = await call_model(
        ModelCallRequest(
            prompt=_CROSS_DOCUMENT.text.format(case_data=case_data),
            system=_SYSTEM.text,
            max_tokens=_CROSS_DOCUMENT_MAX_TOKENS,
            response_model=CrossDocumentAnalysis,
            prompt_id="charge_processing.cross_document",
            prompt_version=compose_version(_SYSTEM, _CROSS_DOCUMENT),
            agent_id="charge_processing",
        )
    )
    return result.data.model_dump()


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


def _empty_analysis() -> dict[str, Any]:
    """Cross-document analysis structure when there are no documents to analyze."""
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
