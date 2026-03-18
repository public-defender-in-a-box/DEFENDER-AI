"""Attorney review endpoints — annotation, edits, comprehension checks."""

from fastapi import APIRouter

router = APIRouter(tags=["review"])


@router.get("/cases/{case_id}/review")
async def get_review_status(case_id: str):
    """Get review status for all sections of a case memo."""
    # TODO: Wire to database
    return {"case_id": case_id, "sections": []}


@router.post("/cases/{case_id}/review/{section_id}/annotate")
async def submit_annotation(case_id: str, section_id: str, data: dict):
    """Submit attorney annotation for a high-stakes section."""
    # TODO: Validate annotation is substantive, save to DB
    return {"status": "annotation_received"}


@router.post("/cases/{case_id}/review/{section_id}/approve")
async def approve_section(case_id: str, section_id: str):
    """Mark a section as attorney-approved."""
    # TODO: Check engagement threshold met for this tier
    return {"status": "approved"}


@router.post("/cases/{case_id}/review/{section_id}/comprehension")
async def comprehension_check(case_id: str, section_id: str, data: dict):
    """Verify attorney comprehension for high-stakes items."""
    # TODO: Check answer against expected keywords
    return {"passed": True}
