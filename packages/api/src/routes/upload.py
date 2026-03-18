"""Document upload and parsing endpoints."""

from fastapi import APIRouter, UploadFile, File, Form

router = APIRouter(tags=["upload"])


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form("COMPLAINT"),
):
    """Upload a charging document and trigger processing.

    Accepts PDF, PNG, JPG. Extracts text and triggers the charge processing pipeline.
    """
    # TODO: Save file, extract text, trigger pipeline
    contents = await file.read()

    return {
        "file_name": file.filename,
        "document_type": document_type,
        "size_bytes": len(contents),
        "status": "uploaded",
        "message": "Document uploaded. Processing pipeline will be triggered.",
    }
