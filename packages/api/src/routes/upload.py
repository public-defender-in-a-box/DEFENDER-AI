"""Document upload and pipeline trigger endpoint."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from src.agents.tier0.orchestrator import OrchestratorAgent
from src.agents.tier1.charge_processing import ChargeProcessingAgent
from src.agents.tier1.pre_interview import PreInterviewResearchAgent
from src.routes._store import case_store
from src.services.document_parser import extract_text_from_image, extract_text_from_pdf
from src.services.storage_service import save_file

logger = logging.getLogger(__name__)

router = APIRouter(tags=["upload"])

_ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt"}


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: str = Form("COMPLAINT"),
    jurisdiction: str = Form("GA"),
    attorney_id: str = Form("default_attorney"),
    case_id: str = Form(""),
):
    """Upload a charging document and trigger the processing pipeline.

    Accepts PDF, PNG, JPG, or TXT files. Extracts text, creates a case,
    and runs Charge Processing + Pre-Interview Research in the background.

    Returns the case_id immediately so you can poll /cases/{case_id}/status.
    """
    filename = file.filename or "document"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {_ALLOWED_EXTENSIONS}",
        )

    contents = await file.read()

    if not case_id:
        case_id = f"CASE-{uuid.uuid4().hex[:8]}"

    # Save file to storage
    storage_url = await save_file(contents, filename)

    # Extract text
    if ext == ".pdf":
        document_text = await extract_text_from_pdf(contents)
    elif ext in (".png", ".jpg", ".jpeg"):
        document_text = await extract_text_from_image(contents)
    elif ext == ".txt":
        document_text = contents.decode("utf-8", errors="replace")
    else:
        document_text = ""

    if not document_text.strip():
        raise HTTPException(
            status_code=422,
            detail="Could not extract any text from the uploaded document.",
        )

    # Create the case via Orchestrator
    orchestrator = OrchestratorAgent()
    await orchestrator.run(
        {
            "case_id": case_id,
            "attorney_id": attorney_id,
            "jurisdiction": jurisdiction,
            "documents": [
                {
                    "id": f"doc-{uuid.uuid4().hex[:8]}",
                    "type": document_type,
                    "file_name": filename,
                    "storage_url": storage_url,
                }
            ],
        }
    )

    # Store orchestrator and document text for pipeline use
    case_store[case_id] = orchestrator

    # Run the pipeline in the background so the upload returns immediately
    background_tasks.add_task(
        _run_pipeline,
        case_id,
        document_text,
        document_type,
        jurisdiction,
    )

    return {
        "case_id": case_id,
        "file_name": filename,
        "document_type": document_type,
        "jurisdiction": jurisdiction,
        "text_length": len(document_text),
        "status": "PROCESSING",
        "summary_url": f"/api/v1/cases/{case_id}/summary",
        "status_url": f"/api/v1/cases/{case_id}/status",
        "message": (
            f"Document uploaded and text extracted ({len(document_text)} chars). "
            f"Pipeline running (~60-90s). "
            f"View results at: /api/v1/cases/{case_id}/summary"
        ),
    }


async def _run_pipeline(
    case_id: str,
    document_text: str,
    document_type: str,
    jurisdiction: str,
) -> None:
    """Run the Tier 1 pipeline: Charge Processing → Pre-Interview Research.

    Runs as a background task after upload returns.
    """
    orchestrator = case_store.get(case_id)
    if not orchestrator:
        logger.error("No orchestrator found for case %s", case_id)
        return

    # --- Charge Processing ---
    can_run, reason = orchestrator.can_run_agent("charge_processing")
    if not can_run:
        logger.error("Cannot run charge_processing for %s: %s", case_id, reason)
        return

    orchestrator.mark_agent_started("charge_processing")

    try:
        charge_agent = ChargeProcessingAgent()
        charge_result = await charge_agent.run(
            {
                "document_text": document_text,
                "document_type": document_type,
                "jurisdiction": jurisdiction,
                "matter_id": case_id,
            }
        )
    except Exception as e:
        await orchestrator.handle_agent_failure("charge_processing", str(e))
        logger.exception("Charge processing failed for %s", case_id)
        return

    merge = await orchestrator.receive_agent_output("charge_processing", charge_result)
    if merge["decision"] == "BLOCKED_ETHICS_P1":
        logger.warning(
            "Charge processing blocked (ethics) for %s: %s",
            case_id,
            merge.get("reason"),
        )
        return
    if merge.get("human_review_required"):
        logger.warning(
            "Charge processing low confidence for %s — merged with flag",
            case_id,
        )

    logger.info("Charge processing complete for %s", case_id)

    # --- Pre-Interview Research ---
    can_run, reason = orchestrator.can_run_agent("pre_interview_research")
    if not can_run:
        logger.error("Cannot run pre_interview for %s: %s", case_id, reason)
        return

    orchestrator.mark_agent_started("pre_interview_research")

    try:
        pre_agent = PreInterviewResearchAgent()
        pre_result = await pre_agent.run(
            {
                "charge_processing": orchestrator.case_state.charge_processing,
            }
        )
    except Exception as e:
        await orchestrator.handle_agent_failure("pre_interview_research", str(e))
        logger.exception("Pre-interview research failed for %s", case_id)
        return

    merge = await orchestrator.receive_agent_output("pre_interview_research", pre_result)
    logger.info(
        "Pre-interview research complete for %s (decision: %s)",
        case_id,
        merge["decision"],
    )

    # --- Intake Conductor (batch mode — no interactive responses) ---
    from src.agents.tier1.intake_conductor import IntakeConductorAgent

    can_run, reason = orchestrator.can_run_agent("intake_conductor")
    if not can_run:
        logger.error("Cannot run intake_conductor for %s: %s", case_id, reason)
        return

    orchestrator.mark_agent_started("intake_conductor")

    charge_data = (
        orchestrator.case_state.charge_processing
        if orchestrator.case_state
        else {}
    ) or {}
    if "data" in charge_data and "confidence" in charge_data:
        charge_data = charge_data["data"]

    try:
        intake_agent = IntakeConductorAgent()
        intake_result = await intake_agent.run(
            {
                "charge_data": charge_data,
                "matter_id": case_id,
                "responses": {},
            }
        )
    except Exception as e:
        await orchestrator.handle_agent_failure("intake_conductor", str(e))
        logger.exception("Intake conductor failed for %s", case_id)
        return

    merge = await orchestrator.receive_agent_output("intake_conductor", intake_result)
    logger.info(
        "Intake conductor complete for %s (decision: %s)",
        case_id,
        merge["decision"],
    )
