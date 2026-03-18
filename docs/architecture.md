# Architecture

## Agent Hierarchy

```
TIER 0 — ORCHESTRATOR
    └── Case Orchestrator (maintains CaseState, manages pipeline)

TIER 1 — CONDUCTORS
    ├── Charge Processing Agent (Step Zero — parses charging docs)
    ├── Pre-Interview Research Conductor (builds legal foundation)
    ├── Intake Conductor (client-facing interview)
    └── Case Prep Conductor (attorney-facing synthesis)

TIER 2 — RESEARCH AGENTS
    ├── Statute Agent (statutory law analysis)
    ├── Case Law Agent (judicial opinions)
    ├── Citation Verification Agent (mechanical verification)
    └── Recency Monitor (background corpus freshness)

TIER 2 — INTAKE SPECIALISTS
    ├── Fact Gathering Agent (core factual interview)
    ├── Rights Violation Scanner (constitutional violations)
    ├── Collateral Consequences Agent (non-criminal consequences)
    └── Personal Circumstances Agent (bail, mitigation, diversion)

TIER 2 — ATTORNEY PREP SPECIALISTS
    ├── Motion Drafter Agent (preliminary motion drafts)
    ├── Brady Compliance Agent (discovery gap analysis)
    ├── Plea/Trial Assessment Agent (decision support)
    └── Sentencing & Mitigation Agent (sentencing exposure)

CROSS-CUTTING
    └── Ethics & Compliance Monitor (guardrails on all agents)
```

## Pipeline Flow

1. Charging docs uploaded → Charge Processing Agent
2. Pre-Interview Research pulls statutes + case law
3. Intake Conductor interviews client
4. Intake sub-agents gather facts, scan rights, assess collateral
5. Case Prep Conductor synthesizes everything
6. Attorney receives: memo, motions, Brady analysis, plea/trial assessment
7. Ethics Monitor runs continuously

## Data Flow

All agents read from and write to the canonical `CaseState` object.
Agents never communicate directly — data flows through the Orchestrator.
