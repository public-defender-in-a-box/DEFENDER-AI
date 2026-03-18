"""Case CRUD endpoints."""

from fastapi import APIRouter

router = APIRouter(tags=["cases"])


@router.get("/cases")
async def list_cases():
    """List all cases for the authenticated attorney."""
    # TODO: Wire to database
    return []


@router.get("/cases/{case_id}")
async def get_case(case_id: str):
    """Get full case state by ID."""
    # TODO: Wire to database
    return {"id": case_id, "stage": "CREATED"}


@router.post("/cases")
async def create_case(data: dict):
    """Create a new case."""
    # TODO: Wire to database + orchestrator
    return {"id": "new_case", "stage": "CREATED"}
