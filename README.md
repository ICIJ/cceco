# cceco

Claude Code environmental impact tracker. Reads local session history and shows energy, GHG, water, metals, and fossil fuel usage via [EcoLogits](https://ecologits.ai).

Also made with Claude code and superpowers.

## Install

```
pipx install cceco
```

## Usage

```
cceco                                        # all time
cceco --since 2026-06-01                     # from a date
cceco --since 2026-06-01 --until 2026-06-09  # date range
cceco --tokens                               # also show token breakdown
```

## Example output

```
Claude Code Environmental Impact
Period: all time  (3 projects, 12 sessions, 47 requests)

── claude-sonnet-4-6 ──────────────────────────────────
Electricity   0.042 kWh  [0.031 – 0.053]
GHG           0.018 kgCO2eq  [0.013 – 0.023]
Water         0.12 L  [0.09 – 0.15]
Abiotic depl. 4.2e-09 kgSbeq  [3.1e-09 – 5.3e-09]
Fossil fuels  0.61 MJ  [0.45 – 0.77]
```

With `--tokens`:

```
── claude-sonnet-4-6 ──────────────────────────────────
Tokens        input: 1,234,567   output: 89,012
              cache creation: 345,678   cache read: 234,567

Electricity   ...
```

## Development

```bash
git clone https://github.com/icij/cceco
cd cceco
uv sync
uv run cceco
uv run pytest
```

## Notes

Impact is calculated using EcoLogits from the total tokens that require GPU
computation per model: `input_tokens + cache_creation_input_tokens +
output_tokens`. Cache-read tokens are excluded because they are cheap
key-value cache lookups rather than full forward passes.

This matches what you would enter manually in the EcoLogits web calculator.
