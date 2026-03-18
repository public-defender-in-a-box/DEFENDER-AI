# Data Contracts

## Overview

All data contracts are defined in two places:
- **TypeScript:** `packages/web/src/types/` (frontend)
- **Python:** `packages/api/src/models/` (backend)

These must stay in sync. The Python Pydantic models are the source of truth.

## Key Types

- `CaseState` — canonical case state, owned by Orchestrator
- `ChargeProcessingInput/Output` — Charge Processing Agent I/O
- `IntakeConductorInput` / `IntakeSummaryOutput` — Intake I/O
- `EthicalFlag` — ethics monitor output
- `ConfidenceRated<T>` — wrapper for all agent outputs

See the type files for full definitions.
