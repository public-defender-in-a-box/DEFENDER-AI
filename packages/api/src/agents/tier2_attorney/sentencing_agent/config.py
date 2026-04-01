"""Configuration for the Sentencing & Mitigation Agent."""

import os
from pathlib import Path

# Agent version
AGENT_VERSION = "0.2.0"

# Feature flags for MVP
ENABLE_UNVERIFIED_RESEARCH = False
ENABLE_VECTOR_SEARCH = False

# Data paths
DATA_DIR = Path(__file__).parent / "data" / "ga"
STATUTES_PATH = DATA_DIR / "statutes.json"
PROGRAM_DIRECTORY_PATH = DATA_DIR / "program_directory.json"
COMPARABLES_PATH = DATA_DIR / "marijuana_comparables.json"

# Confidence weights for output assembler
CONFIDENCE_WEIGHTS = {
    "scope_validation": 0.20,
    "criminal_history_verified": 0.20,
    "local_context_present": 0.15,
    "diversion_availability_quality": 0.10,
    "mitigation_fact_coverage": 0.15,
    "comparable_sentence_quality": 0.10,
    "llm_outputs_schema_valid": 0.10,
}

# Confidence caps
MAX_CONFIDENCE_OUT_OF_SCOPE = 0.40
MAX_CONFIDENCE_SELF_REPORTED_HISTORY = 0.55

# Max comparables to return
MAX_COMPARABLES = 5
MIN_COMPARABLES_WARNING_THRESHOLD = 2
