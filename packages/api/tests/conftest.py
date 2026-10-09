"""Shared test fixtures.

Two autouse guards make "zero live network calls in CI" enforceable rather than
aspirational (PHASE_1_MODEL_GATEWAY.md §5.2):

- the model gateway runs in ``replay`` mode with no API key, so a missing cassette
  raises ``CassetteMissError`` instead of reaching the API;
- every outbound socket connection and DNS lookup is refused, and any attempt fails
  the test that made it — even if agent code swallowed the error.

The one exception is a deliberate recording pass: ``MODEL_GATEWAY_MODE=record`` in the
environment, with the recorder's own ``ANTHROPIC_API_KEY`` (§5.5).
"""

import ipaddress
import os
import socket
from collections.abc import Iterator

import pytest

from src.config import settings
from src.services import measurements
from src.services.model_gateway import gateway


class LiveNetworkBlocked(RuntimeError):
    """A test tried to reach the network."""


def _test_mode() -> str:
    mode = os.getenv("MODEL_GATEWAY_MODE", "replay")
    if mode not in ("replay", "record"):
        raise pytest.UsageError(
            f"MODEL_GATEWAY_MODE={mode!r} is not allowed under pytest: use replay "
            "(default) or record."
        )
    return mode


def _is_loopback(host: object) -> bool:
    if not isinstance(host, str):
        return False
    if host in ("localhost", "testserver"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def gateway_test_mode(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    mode = _test_mode()
    monkeypatch.setattr(settings, "MODEL_GATEWAY_MODE", mode)
    if mode == "replay":
        # Replay needs no key; making sure there is none means nothing can spend one.
        monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
        monkeypatch.setattr(settings, "COURTLISTENER_API_KEY", "")
    gateway.set_client(None)
    gateway.set_store(None)
    measurements.clear()
    yield mode
    gateway.set_client(None)
    gateway.set_store(None)


@pytest.fixture(autouse=True)
def network_guard(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Refuse outbound connections; fail the test at teardown if any were attempted."""
    attempts: list[str] = []
    if _test_mode() == "record":
        yield attempts
        return

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo

    def _allowed(sock: socket.socket, address: object) -> bool:
        if sock.family == getattr(socket, "AF_UNIX", None):
            return True
        return isinstance(address, tuple) and _is_loopback(address[0])

    def guarded_connect(sock: socket.socket, address: object) -> None:
        if not _allowed(sock, address):
            attempts.append(f"connect {address}")
            raise LiveNetworkBlocked(f"Live network access blocked in tests: {address}")
        real_connect(sock, address)

    def guarded_connect_ex(sock: socket.socket, address: object) -> int:
        if not _allowed(sock, address):
            attempts.append(f"connect {address}")
            raise LiveNetworkBlocked(f"Live network access blocked in tests: {address}")
        return real_connect_ex(sock, address)

    def guarded_getaddrinfo(host: object, *args: object, **kwargs: object) -> object:
        if host is not None and not _is_loopback(host):
            attempts.append(f"dns {host}")
            raise LiveNetworkBlocked(f"Live DNS lookup blocked in tests: {host}")
        return real_getaddrinfo(host, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    yield attempts
    if attempts:
        pytest.fail(
            "Test attempted live network access (blocked): " + "; ".join(attempts),
            pytrace=False,
        )


@pytest.fixture
def sample_complaint_text() -> str:
    """Sample criminal complaint text for testing."""
    return """
STATE OF GEORGIA
IN THE STATE COURT OF FULTON COUNTY

THE STATE OF GEORGIA
v.
JOHN DOE

ACCUSATION

The undersigned complainant states that on or about January 15, 2024,
at approximately 2:30 AM, in the City of Atlanta, County of Fulton,
State of Georgia:

COUNT I - POSSESSION OF A CONTROLLED SUBSTANCE
O.C.G.A. § 16-13-30(a)

The defendant, JOHN DOE, knowingly possessed less than one ounce of
a substance containing cocaine, a controlled substance listed in
Schedule II of the Georgia Controlled Substances Act.

The defendant was observed by Officer James Smith, Badge #4521,
Atlanta Police Department, Zone 3, standing near the intersection
of Peachtree St and Andrew Young International Blvd. Officer Smith
observed the defendant discard a small plastic bag containing a white
powdery substance. Field testing confirmed the substance to be cocaine,
weighing approximately 2.3 grams.

Witness: Officer Maria Garcia, Badge #3847, APD Zone 3
    """


@pytest.fixture
def sample_case_state() -> dict:
    """Minimal case state for testing."""
    return {
        "id": "test_case_001",
        "jurisdiction": "GA",
        "stage": "CREATED",
        "attorney_id": "attorney_001",
        "documents": [],
    }
