"""Response models for model calls: one module per agent (PHASE_1_MODEL_GATEWAY.md §2).

Each is the schema the gateway enforces with structured outputs. Free-form ``dict``
fields cannot be expressed there (they would be constrained to ``{}``), so nested
structure is always a typed model or a list of them.
"""
