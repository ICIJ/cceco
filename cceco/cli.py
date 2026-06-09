from __future__ import annotations

import argparse
import sys
from datetime import date

from .impact import ImpactRange, compute_impact
from .reader import read_usage


def _fmt_range(r: ImpactRange) -> str:
    return f"{r.mean:.3g} {r.unit}  [{r.min:.3g} – {r.max:.3g}]"


def _fmt_tokens(n: int) -> str:
    return f"{n:,}"


def _parse_date(value: str | None, flag: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        print(f"Error: invalid date for {flag}: '{value}'. Expected YYYY-MM-DD, e.g. {flag} 2026-06-01")
        sys.exit(1)


def _print_metric(label: str, r: ImpactRange) -> None:
    print(f"{label:<14}{_fmt_range(r)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cceco",
        description="Claude Code environmental impact tracker",
    )
    parser.add_argument("--since", metavar="YYYY-MM-DD",
                        help="Include sessions from this date (inclusive)")
    parser.add_argument("--until", metavar="YYYY-MM-DD",
                        help="Include sessions up to this date (inclusive)")
    args = parser.parse_args()

    since = _parse_date(args.since, "--since")
    until = _parse_date(args.until, "--until")

    usage, project_count, session_count, malformed = read_usage(since=since, until=until)

    if not usage:
        if since or until:
            print("No sessions found in the specified period.")
        else:
            print("No Claude Code session data found.")
        sys.exit(0)

    period = "all time"
    if since and until:
        period = f"{since} to {until}"
    elif since:
        period = f"since {since}"
    elif until:
        period = f"until {until}"

    total_requests = sum(u.request_count for u in usage.values())
    print("Claude Code Environmental Impact")
    print(f"Period: {period}  ({project_count} projects, {session_count} sessions, {total_requests} requests)")
    print()

    totals: dict[str, list[float]] = {
        k: [0.0, 0.0, 0.0]
        for k in ("electricity", "ghg", "water", "metals", "fossil_fuels")
    }
    models_with_impact = 0

    for model, u in sorted(usage.items()):
        bar = "─" * max(0, 54 - len(model) - 4)
        print(f"── {model} {bar}")
        print(f"Tokens        input: {_fmt_tokens(u.input_tokens)}   output: {_fmt_tokens(u.output_tokens)}")
        print(f"              cache creation: {_fmt_tokens(u.cache_creation_input_tokens)}   cache read: {_fmt_tokens(u.cache_read_input_tokens)}")
        print()

        # Tokens requiring GPU compute: input prefill + cache creation + generation.
        # Cache reads are cheap KV-cache lookups and excluded.
        effective_tokens = u.input_tokens + u.cache_creation_input_tokens + u.output_tokens
        impact = compute_impact(model, effective_tokens) if effective_tokens > 0 else None
        if impact is None:
            print(f"  Warning: model '{model}' not recognized by ecologits — impact not computed.")
        else:
            models_with_impact += 1
            _print_metric("Electricity", impact.electricity)
            _print_metric("GHG", impact.ghg)
            _print_metric("Water", impact.water)
            _print_metric("Abiotic depl.", impact.metals)
            _print_metric("Fossil fuels", impact.fossil_fuels)

            for key, imp in [
                ("electricity", impact.electricity),
                ("ghg", impact.ghg),
                ("water", impact.water),
                ("metals", impact.metals),
                ("fossil_fuels", impact.fossil_fuels),
            ]:
                totals[key][0] += imp.min
                totals[key][1] += imp.mean
                totals[key][2] += imp.max

        print()

    if models_with_impact >= 2:
        print("══ TOTAL ══════════════════════════════════════════════")
        units = {"electricity": "kWh", "ghg": "kgCO2eq", "water": "L",
                 "metals": "kgSbeq", "fossil_fuels": "MJ"}
        labels = {"electricity": "Electricity", "ghg": "GHG", "water": "Water",
                  "metals": "Abiotic depl.", "fossil_fuels": "Fossil fuels"}
        for key in ("electricity", "ghg", "water", "metals", "fossil_fuels"):
            mn, mean, mx = totals[key]
            _print_metric(labels[key], ImpactRange(min=mn, mean=mean, max=mx, unit=units[key]))
        print()

    if malformed:
        print(f"Skipped {malformed} malformed records.")


if __name__ == "__main__":
    main()
