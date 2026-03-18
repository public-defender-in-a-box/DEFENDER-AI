"""Shared test fixtures."""

import pytest


@pytest.fixture
def sample_complaint_text() -> str:
    """Sample criminal complaint text for testing."""
    return """
STATE OF ILLINOIS
IN THE CIRCUIT COURT OF COOK COUNTY

THE PEOPLE OF THE STATE OF ILLINOIS
v.
JOHN DOE

COMPLAINT

The undersigned complainant states that on or about January 15, 2024,
at approximately 2:30 AM, in the City of Chicago, County of Cook,
State of Illinois:

COUNT I - POSSESSION OF A CONTROLLED SUBSTANCE
720 ILCS 570/402(c)

The defendant, JOHN DOE, knowingly possessed less than 15 grams of
a substance containing cocaine, a controlled substance listed in
Schedule II of the Illinois Controlled Substances Act.

The defendant was observed by Officer James Smith, Badge #4521,
Chicago Police Department, 11th District, standing near the intersection
of W. Roosevelt Rd and S. Halsted St. Officer Smith observed the
defendant discard a small plastic bag containing a white powdery
substance. Field testing confirmed the substance to be cocaine,
weighing approximately 2.3 grams.

Witness: Officer Maria Garcia, Badge #3847, CPD 11th District
    """


@pytest.fixture
def sample_case_state() -> dict:
    """Minimal case state for testing."""
    return {
        "id": "test_case_001",
        "jurisdiction": "IL",
        "stage": "CREATED",
        "attorney_id": "attorney_001",
        "documents": [],
    }
