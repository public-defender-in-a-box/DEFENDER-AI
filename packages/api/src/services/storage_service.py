"""File storage service — local filesystem for MVP, S3-compatible later."""

import uuid
from pathlib import Path

from src.config import settings


async def save_file(file_bytes: bytes, filename: str) -> str:
    """Save an uploaded file and return the storage path."""
    storage_dir = Path(settings.STORAGE_PATH)
    storage_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename to prevent collisions
    ext = Path(filename).suffix
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = storage_dir / unique_name

    file_path.write_bytes(file_bytes)

    return str(file_path)


async def read_file(storage_url: str) -> bytes:
    """Read a file from storage."""
    return Path(storage_url).read_bytes()
