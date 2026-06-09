# cceco — Design Spec
**Date:** 2026-06-09

## Overview

`cceco` is a Python CLI utility that reads Claude Code's local session history and computes the environmental impact of that AI usage using the `ecologits` library. It is published on PyPI and installed with `pipx`.

```
pipx install cceco
cceco                                   # all time
cceco --since 2026-06-01                # from a date
cceco --since 2026-06-01 --until 2026-06-09
```

## Packaging

| Field | Value |
|---|---|
| Package name | `cceco` |
| Command | `cceco` |
| Python | ≥ 3.11 |
| Build system | Poetry |
| Distribution | PyPI via `pipx install cceco` |
| Dependencies | `ecologits` |

`pyproject.toml` entry point:
```toml
[tool.poetry.scripts]
cceco = "cceco.cli:main"
```

## Project Structure

```
cceco/
├── pyproject.toml
├── README.md
└── cceco/
    ├── __init__.py
    ├── cli.py        # argparse, orchestration
    ├── reader.py     # JSONL scanning and token aggregation
    └── impact.py     # ecologits wrapper
```

## Data Source

Claude Code writes one JSONL file per session under:
```
~/.claude/projects/<project-slug>/<session-uuid>.jsonl
```

Each line is a JSON record. Records where `type == "assistant"` carry:
- `timestamp` — ISO 8601 string, used for date filtering
- `message.model` — e.g. `"claude-sonnet-4-6"`
- `message.usage.input_tokens`
- `message.usage.cache_creation_input_tokens`
- `message.usage.cache_read_input_tokens`
- `message.usage.output_tokens`

The script walks `~/.claude/projects/` recursively, reads every `*.jsonl` file, skips malformed lines, and filters by `timestamp` when `--since`/`--until` are given (`YYYY-MM-DD` format, inclusive bounds).

## Token Aggregation

Tokens are accumulated per model:

```python
{
  "claude-sonnet-4-6": {
    "input_tokens": int,
    "cache_creation_input_tokens": int,
    "cache_read_input_tokens": int,
    "output_tokens": int,
    "request_count": int,
  },
  ...
}
```

## EcoLogits Integration

`llm_impacts()` from `ecologits.tracers.utils` is called once per model:

```python
impacts = llm_impacts(
    provider="anthropic",
    model_name=model,           # e.g. "claude-sonnet-4-6"
    output_token_count=totals["output_tokens"],
    request_latency=None,       # not available in logs; ecologits uses a statistical estimate
)
```

**Approximation note:** `llm_impacts()` does not accept `input_token_count` separately. Input and cache tokens are not passed to the function; the calculation is based on output tokens and model architecture data. This matches how the EcoLogits calculator web UI works. The token breakdown (input/cache/output) is still displayed for informational purposes.

If a model name is not recognized by ecologits, the script emits a warning and skips impact computation for that model while still showing its token counts.

### Metrics displayed

All five metrics from the `Impacts` object, each shown as `mean [min – max]`:

| Metric | Field | Unit |
|---|---|---|
| Electricity | `energy.value` | kWh |
| GHG | `gwp.value` | kgCO2eq |
| Water | `wcf.value` | L |
| Metals & minerals | `adpe.value` | kgSbeq |
| Fossil fuels | `pe.value` | MJ |

## Output Format

```
Claude Code Environmental Impact
Period: all time  (3 projects, 12 sessions, 47 requests)

── claude-sonnet-4-6 ──────────────────────────────────
Tokens        input: 1,234,567   output: 89,012
              cache creation: 345,678   cache read: 234,567

Electricity   0.042 kWh  [0.031 – 0.053]
GHG           0.018 kgCO2eq  [0.013 – 0.023]
Water         0.12 L  [0.09 – 0.15]
Metals        4.2e-8 kgSbeq  [3.1e-8 – 5.3e-8]
Fossil fuels  0.61 MJ  [0.45 – 0.77]

── claude-opus-4-8 ────────────────────────────────────
...

══ TOTAL ══════════════════════════════════════════════
Electricity   0.065 kWh  [0.048 – 0.082]
GHG           0.027 kgCO2eq  [0.020 – 0.034]
Water         0.19 L  [0.14 – 0.24]
Metals        6.5e-8 kgSbeq  [4.8e-8 – 8.2e-8]
Fossil fuels  0.94 MJ  [0.69 – 1.19]
```

## CLI Arguments

| Argument | Type | Default | Description |
|---|---|---|---|
| `--since` | `YYYY-MM-DD` | none | Include sessions from this date (inclusive). Can be used alone or with `--until`. |
| `--until` | `YYYY-MM-DD` | none | Include sessions up to this date (inclusive). Can be used alone or with `--since`. |

## Error Handling

| Situation | Behaviour |
|---|---|
| `ecologits` not installed | Caught at import; exits with install instruction (shouldn't happen via pipx) |
| `~/.claude/projects/` missing | Clear message: "No Claude Code session data found." |
| No records match date filter | "No sessions found in the specified period." |
| Malformed JSON line | Skipped silently; count reported at end: "Skipped N malformed records." |
| Unknown model name | Warning per model: "Model X not recognized by ecologits — impact not computed." Token counts still shown. |
| Invalid date format | Exits with usage hint: "Expected YYYY-MM-DD, e.g. --since 2026-06-01" |
