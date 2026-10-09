# Models

What the system calls, how, and at what price. Required by
`PHASE_1_MODEL_GATEWAY.md` §8; update it whenever any of this changes, and re-check
the live documentation before every recording pass rather than trusting this file.

Checked **October 9, 2026** against Anthropic's live documentation:

- Models: <https://platform.claude.com/docs/en/about-claude/models/overview>
- Deprecations: <https://platform.claude.com/docs/en/about-claude/model-deprecations>
- Pricing: <https://platform.claude.com/docs/en/about-claude/pricing>
- Structured outputs (supported models, schema limits):
  <https://platform.claude.com/docs/en/build-with-claude/structured-outputs>

## Decisions

| | Value | Source of the decision |
|---|---|---|
| Primary model | `claude-opus-5-5` | Team, October 9, 2026 (`PHASE_1_MODEL_GATEWAY.md` §0.1) |
| Comparison model (recorded) | `claude-sonnet-5-5` | Team, October 9, 2026 — confirmed before any recording |
| Allowlist (`CLAUDE_MODELS_ALLOWED`) | `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5` | Team: users may switch a run to a cheaper model |
| Haiku 5.5 | Selectable for cost, **live only**: no recordings | `PHASE_1_MODEL_GATEWAY.md` §8 |
| Effort | `high` for every call, every model | §5.3: the models' own defaults differ |
| Automatic model fallbacks | Off; none implemented | Team (§0.3) |
| API key | Each user's own `ANTHROPIC_API_KEY` | Team (§0.5, §8.1) |
| Python SDK | `anthropic==1.11.0` (pinned in `requirements.txt` and `pyproject.toml`) | §2 |

## The models

| Model | ID | Thinking | Default effort | Context | Retirement, not sooner than |
|---|---|---|---|---|---|
| Claude Opus 5.5 | `claude-opus-5-5` | Always on | `medium` | 1M | September 22, 2027 |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | Adaptive | `high` | 1M | September 28, 2027 |
| Claude Haiku 5.5 | `claude-haiku-5-5` | Adaptive | `medium` | 1M | October 7, 2027 |

Dateless IDs are pinned snapshots. All three support structured outputs. The old
default, `claude-sonnet-4-20250514`, was retired on June 15, 2026; it is not on the
allowlist and the gateway rejects it.

**Resolved `model_returned`** (the model ID each response reports): *not yet
observed* — no live call has been made from this repository. The gateway records it
on every call and every cassette stores the response's `model` field; fill this in
from the recording pass.

## Prices

From `packages/api/src/services/model_gateway/pricing.json` (the gateway's only
source of prices), per million tokens, standard rates:

| Model | Input | Output | Cache write (5 min) | Cache read |
|---|---|---|---|---|
| `claude-opus-5-5` | $4.00 | $20.00 | $5.00 | $0.20 |
| `claude-sonnet-5-5` | $2.00 | $10.00 | $2.50 | $0.10 |
| `claude-haiku-5-5`, prompt ≤ 100K tokens | $0.10 | $0.50 | $0.125 | $0.01 |
| `claude-haiku-5-5`, prompt > 100K tokens | $0.50 | $2.50 | $0.625 | $0.05 |

A Haiku 5.5 request's prompt length counts input, cache-read and cache-write tokens;
the whole request is priced at its tier.

## How every call is made

`services/model_gateway.call_model` (one call path; there is no other):

- **Structured outputs** constrain each reply to its response model's JSON schema
  (`output_config.format`). A response model may not contain a free-form `dict`
  field: structured outputs would constrain it to `{}`, so the gateway refuses it
  before calling.
- **No `temperature`, `top_p`, `top_k`, `thinking` or `fallbacks`** in any request.
- `stop_reason` is checked before content: `refusal` → `RefusalError`,
  `max_tokens` → `TruncatedResponseError`. Text blocks are joined; thinking blocks
  (first on these models) are skipped.
- **Retries and timeout** are explicit: `MODEL_GATEWAY_MAX_RETRIES` (default 2) and
  `MODEL_GATEWAY_TIMEOUT_S` (default 600). The SDK retries 408/409/429/5xx and
  connection errors; the gateway records how many retries it took.
- **Every call is recorded** (success or failure) as a `MODEL_CALL` measurement:
  agent, prompt id and version, model requested and returned, effort, tokens,
  latency, retries, cassette outcome, cost, outcome, abstention.
- `max_tokens` is set per call site (4,000–24,000): thinking tokens count toward it.

## Recording pass (outstanding)

Cassettes are recorded by a team member with their own key, for the primary and the
comparison model, then committed. CourtListener cassettes need network access to
`www.courtlistener.com` (the shared cloud environment's network policy denies it);
check at recording time that its v3 API is still served.

```bash
cd packages/api
export ANTHROPIC_API_KEY=...            # your own key; never commit it
export COURTLISTENER_API_KEY=...        # optional, your own
MODEL_GATEWAY_MODE=record pytest -m recorded
MODEL_GATEWAY_MODE=record CLAUDE_MODEL_PRIMARY=claude-sonnet-5-5 pytest -m recorded
pytest tests/test_cassettes.py          # scan before committing
python ../../scripts/inventory.py       # cassette counts, sizes and recording cost
```

Record mode refuses any call not wrapped in `using_fixtures(...)`, so only committed
synthetic fixtures can be recorded. CI replays the primary's cassettes on every run
and the comparison model's in a second `pytest -m recorded` step.
