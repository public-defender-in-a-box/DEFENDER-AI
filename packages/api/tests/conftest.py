"""Shared test fixtures."""

import pytest


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
