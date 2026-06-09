from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass
class ModelUsage:
    input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    output_tokens: int = 0
    request_count: int = 0


def read_usage(
    since: date | None = None,
    until: date | None = None,
    projects_dir: Path | None = None,
) -> tuple[dict[str, ModelUsage], int, int, int]:
    """Scan Claude Code session logs and aggregate token usage per model.

    Returns (usage_per_model, project_count, session_count, malformed_count).
    """
    if projects_dir is None:
        projects_dir = Path.home() / ".claude" / "projects"

    if not projects_dir.exists():
        return {}, 0, 0, 0

    usage: dict[str, ModelUsage] = {}
    seen_projects: set[str] = set()
    seen_sessions: set[str] = set()
    malformed_count = 0

    for jsonl_file in sorted(projects_dir.rglob("*.jsonl")):
        for line in jsonl_file.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                malformed_count += 1
                continue

            if record.get("type") != "assistant":
                continue

            message = record.get("message", {})
            usage_data = message.get("usage")
            if usage_data is None:
                continue

            if since or until:
                ts = record.get("timestamp", "")
                if ts:
                    try:
                        record_date = date.fromisoformat(ts[:10])  # timestamps are UTC; compare as UTC dates
                        if since and record_date < since:
                            continue
                        if until and record_date > until:
                            continue
                    except ValueError:
                        pass

            model = message.get("model") or "unknown"
            if model not in usage:
                usage[model] = ModelUsage()

            u = usage[model]
            u.input_tokens += usage_data.get("input_tokens", 0)
            u.cache_creation_input_tokens += usage_data.get("cache_creation_input_tokens", 0)
            u.cache_read_input_tokens += usage_data.get("cache_read_input_tokens", 0)
            u.output_tokens += usage_data.get("output_tokens", 0)
            u.request_count += 1

            seen_projects.add(jsonl_file.parent.name)
            seen_sessions.add(jsonl_file)

    return usage, len(seen_projects), len(seen_sessions), malformed_count
