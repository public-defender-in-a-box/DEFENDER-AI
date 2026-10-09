"""Per-run model selection through the API (PHASE_1_MODEL_GATEWAY.md §8).

A case may run on a cheaper allowlisted model to manage cost; anything off the
allowlist is rejected before any work is done. The UI control is Phase 2b.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.routes._store import case_store
from src.services import measurements

ACCUSATION = (Path(__file__).parent / "fixtures" / "sample_accusation.txt").read_bytes()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setattr("src.config.settings.STORAGE_PATH", str(tmp_path))
    return TestClient(app)


def _upload(client: TestClient, case_id: str, model: str = "") -> object:
    return client.post(
        "/api/v1/upload",
        files={"file": ("accusation.txt", ACCUSATION, "text/plain")},
        data={"case_id": case_id, "document_type": "accusation", "model": model},
    )


def test_off_allowlist_model_is_rejected(client: TestClient) -> None:
    response = _upload(client, "SYN-MODEL-001", model="claude-sonnet-4-20250514")
    assert response.status_code == 422
    assert "allowlist" in response.json()["detail"]
    assert "SYN-MODEL-001" not in case_store


def test_selected_model_runs_the_case(client: TestClient) -> None:
    try:
        response = _upload(client, "SYN-MODEL-002", model="claude-haiku-5-5")
        assert response.status_code == 200
        assert response.json()["model"] == "claude-haiku-5-5"
        status = client.get("/api/v1/cases/SYN-MODEL-002/status").json()
        assert status["model"] == "claude-haiku-5-5"

        # The background pipeline ran in replay mode with no recording, so Charge
        # Processing failed loudly; the failed call shows the model it asked for.
        (failure,) = measurements.events(measurements.MeasurementKind.AGENT_FAILURE)
        assert failure.payload["error_type"] == "CassetteMissError"
        assert failure.payload["model_call"]["model_requested"] == "claude-haiku-5-5"
    finally:
        case_store.pop("SYN-MODEL-002", None)


def test_default_is_the_primary(client: TestClient) -> None:
    try:
        response = _upload(client, "SYN-MODEL-003")
        assert response.json()["model"] == "claude-opus-5-5"
    finally:
        case_store.pop("SYN-MODEL-003", None)
