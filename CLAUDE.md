# CLAUDE.md — Public Defender AI Assistant

## Project Overview
A 19-agent AI system that assists public defenders with client intake, legal
research, case preparation, and attorney workflow. Built by a team of 4 law
students.

## Architecture
- **19 agents** across 3 tiers + 1 cross-cutting ethics layer
- **Pipeline:** Charge Processing → Pre-Interview Research → Client Intake → Case Prep → Attorney Review
- **Canonical state:** Every agent reads from and writes to a single `CaseState` object owned by the Orchestrator
- See `docs/architecture.md` for the full agent hierarchy diagram

## Tech Stack
- **Frontend:** Next.js 14 (App Router, TypeScript) in `packages/web/`
- **Backend:** FastAPI (Python) in `packages/api/`
- **Agent Orchestration:** LangGraph — graph defined in `packages/api/src/agents/graph.py`
- **LLM:** Claude (Anthropic API) — all prompts go through `llm_service.py`
- **Database:** PostgreSQL via Prisma (`packages/web/prisma/schema.prisma`)
- **Monorepo:** Turborepo

## Key Commands
```bash
# Start both frontend and backend
npm run dev

# Frontend only
cd packages/web && npm run dev

# Backend only
cd packages/api && uvicorn src.main:app --reload

# Run Python tests
cd packages/api && pytest

# Run frontend tests
cd packages/web && npm test

# Database migrations
cd packages/web && npx prisma migrate dev

# Format
npm run format          # runs prettier + black
```

## Code Conventions

### Python (packages/api/)
- Python 3.11+
- Pydantic v2 for all data models
- Every agent inherits from `BaseAgent` in `agents/base_agent.py`
- Agent files: one agent per file, named after the agent (e.g., `charge_processing.py`)
- All agent outputs must include a `confidence: ConfidenceLevel` field
- Use `ConfidenceRated[T]` wrapper for all data passed to CaseState
- Type hints everywhere. No `Any` unless unavoidable.

### TypeScript (packages/web/)
- Strict TypeScript — no `any`
- Types live in `src/types/` — shared between frontend and API client
- Components in `src/components/` — organized by feature domain
- API calls go through `src/lib/api-client.ts` — never raw fetch in components
- Use server components by default, client components only when interactive

### Agents
- Every agent has: inputs, outputs, responsibilities (defined in the spec)
- Agents NEVER communicate directly — all data flows through CaseState via the Orchestrator
- Confidence scores are mandatory: HIGH (>0.85), MEDIUM (0.6-0.85), LOW (<0.6)
- Sub-threshold outputs (LOW confidence) are flagged, not presented as reliable
- Ethics Monitor runs on every agent output before it's written to CaseState

### Legal/Ethical Rules (NON-NEGOTIABLE)
- Client-facing agents INFORM, never ADVISE. No legal conclusions to clients.
- Every output that reaches the attorney includes a privilege warning
- All citations tagged with verification status (VERIFIED/UNVERIFIED)
- No client data in logs, error messages, or anywhere outside encrypted storage
- Plea/trial assessments always marked "DECISION SUPPORT ONLY"
- Attorney can override any recommendation — system logs but does not resist
- Draft motions always marked "DRAFT — ATTORNEY REVIEW REQUIRED"

## Agent Map (quick reference)

| Agent | File | Tier | Depends On |
|-------|------|------|------------|
| Case Orchestrator | `tier0/orchestrator.py` | 0 | — |
| Charge Processing | `tier1/charge_processing.py` | 1 | Orchestrator |
| Pre-Interview Research | `tier1/pre_interview.py` | 1 | Charge Processing |
| Intake Conductor | `tier1/intake_conductor.py` | 1 | Pre-Interview Research |
| Case Prep Conductor | `tier1/case_prep.py` | 1 | Intake Conductor |
| Statute Agent | `tier2_research/statute_agent.py` | 2 | Charge Processing |
| Case Law Agent | `tier2_research/case_law_agent.py` | 2 | Pre-Interview Research |
| Citation Verifier | `tier2_research/citation_verifier.py` | 2 | Case Law, Statute |
| Recency Monitor | `tier2_research/recency_monitor.py` | 2 | (background) |
| Fact Gatherer | `tier2_intake/fact_gatherer.py` | 2 | Intake Conductor |
| Rights Scanner | `tier2_intake/rights_scanner.py` | 2 | Pre-Interview, Intake |
| Collateral Agent | `tier2_intake/collateral_agent.py` | 2 | Charge Processing, Intake |
| Personal Circumstances | `tier2_intake/personal_circumstances.py` | 2 | Intake Conductor |
| Motion Drafter | `tier2_attorney/motion_drafter.py` | 2 | Case Prep |
| Brady Agent | `tier2_attorney/brady_agent.py` | 2 | Case Prep |
| Plea/Trial Analyst | `tier2_attorney/plea_trial_analyst.py` | 2 | Case Prep |
| Sentencing Agent | `tier2_attorney/sentencing_agent.py` | 2 | Case Prep |
| Ethics Monitor | `cross_cutting/ethics_monitor.py` | X | All agents |

## Database
- Schema defined in Prisma: `packages/web/prisma/schema.prisma`
- Main tables: `Case`, `Charge`, `Document`, `User`, `IntakeSession`, `AuditLog`
- CaseState stored as JSONB column on the `Case` table for flexibility
- Structured data (charges, users) in normalized tables for querying

## Testing
- Python: pytest with fixtures in `tests/fixtures/`
- Sample charging documents for testing in `tests/fixtures/`
- Every agent needs at least one golden-output test
- Integration tests: upload doc → verify CaseState after pipeline runs

## MVP Scope
- **Single jurisdiction:** Georgia
- **Single case type:** Criminal law (O.C.G.A. Title 16 - Crimes and Offenses)
- **Simplified agents for MVP:**
  - Personal Circumstances → structured form, not conversational
  - Recency Monitor → manual corpus updates
  - Fact Gatherer → integrated into Intake Conductor
  - Case Law Agent → closed corpus only, no open research
