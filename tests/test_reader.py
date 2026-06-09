import json
from datetime import date
from pathlib import Path

import pytest

from cceco.reader import ModelUsage, read_usage


def _write_session(projects_dir: Path, project: str, session: str, records: list[dict]) -> None:
    session_dir = projects_dir / project
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / f"{session}.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records)
    )


def _assistant(model: str, ts: str, **tokens) -> dict:
    return {
        "type": "assistant",
        "timestamp": ts,
        "message": {
            "model": model,
            "usage": {
                "input_tokens": tokens.get("input", 0),
                "cache_creation_input_tokens": tokens.get("cache_creation", 0),
                "cache_read_input_tokens": tokens.get("cache_read", 0),
                "output_tokens": tokens.get("output", 0),
            },
        },
    }


def test_returns_empty_when_projects_dir_missing(tmp_path):
    usage, projects, sessions, malformed = read_usage(projects_dir=tmp_path / "missing")
    assert usage == {}
    assert projects == 0
    assert sessions == 0
    assert malformed == 0


def test_aggregates_tokens_by_model(tmp_path):
    _write_session(tmp_path, "proj-a", "session-1", [
        _assistant("claude-sonnet-4-6", "2026-06-01T10:00:00Z",
                   input=100, cache_creation=200, cache_read=300, output=50),
        _assistant("claude-sonnet-4-6", "2026-06-02T10:00:00Z",
                   input=50, cache_read=100, output=25),
    ])

    usage, _, _, malformed = read_usage(projects_dir=tmp_path)

    assert malformed == 0
    assert "claude-sonnet-4-6" in usage
    u = usage["claude-sonnet-4-6"]
    assert u.input_tokens == 150
    assert u.cache_creation_input_tokens == 200
    assert u.cache_read_input_tokens == 400
    assert u.output_tokens == 75
    assert u.request_count == 2


def test_ignores_non_assistant_records(tmp_path):
    _write_session(tmp_path, "proj-a", "session-1", [
        {"type": "user", "timestamp": "2026-06-01T10:00:00Z", "message": {"content": "hello"}},
        _assistant("claude-sonnet-4-6", "2026-06-01T10:01:00Z", output=10),
    ])

    usage, _, _, _ = read_usage(projects_dir=tmp_path)
    assert list(usage.keys()) == ["claude-sonnet-4-6"]


def test_counts_projects_and_sessions(tmp_path):
    _write_session(tmp_path, "proj-a", "session-1",
                   [_assistant("claude-sonnet-4-6", "2026-06-01T10:00:00Z", output=10)])
    _write_session(tmp_path, "proj-a", "session-2",
                   [_assistant("claude-sonnet-4-6", "2026-06-01T11:00:00Z", output=10)])
    _write_session(tmp_path, "proj-b", "session-3",
                   [_assistant("claude-sonnet-4-6", "2026-06-01T12:00:00Z", output=10)])

    _, projects, sessions, _ = read_usage(projects_dir=tmp_path)
    assert projects == 2
    assert sessions == 3


def test_date_filter_since(tmp_path):
    _write_session(tmp_path, "proj-a", "session-1", [
        _assistant("claude-sonnet-4-6", "2026-06-01T10:00:00Z", output=50),
        _assistant("claude-sonnet-4-6", "2026-06-03T10:00:00Z", output=25),
    ])

    usage, _, _, _ = read_usage(since=date(2026, 6, 2), projects_dir=tmp_path)
    assert usage["claude-sonnet-4-6"].output_tokens == 25


def test_date_filter_until(tmp_path):
    _write_session(tmp_path, "proj-a", "session-1", [
        _assistant("claude-sonnet-4-6", "2026-06-01T10:00:00Z", output=50),
        _assistant("claude-sonnet-4-6", "2026-06-03T10:00:00Z", output=25),
    ])

    usage, _, _, _ = read_usage(until=date(2026, 6, 2), projects_dir=tmp_path)
    assert usage["claude-sonnet-4-6"].output_tokens == 50


def test_date_filter_since_and_until(tmp_path):
    _write_session(tmp_path, "proj-a", "session-1", [
        _assistant("claude-sonnet-4-6", "2026-05-31T10:00:00Z", output=100),
        _assistant("claude-sonnet-4-6", "2026-06-01T10:00:00Z", output=50),
        _assistant("claude-sonnet-4-6", "2026-06-03T10:00:00Z", output=25),
        _assistant("claude-sonnet-4-6", "2026-06-05T10:00:00Z", output=10),
    ])

    usage, _, _, _ = read_usage(
        since=date(2026, 6, 1), until=date(2026, 6, 3), projects_dir=tmp_path
    )
    assert usage["claude-sonnet-4-6"].output_tokens == 75


def test_skips_malformed_lines(tmp_path):
    session_dir = tmp_path / "proj-a"
    session_dir.mkdir(parents=True)
    (session_dir / "session.jsonl").write_text(
        json.dumps(_assistant("claude-sonnet-4-6", "2026-06-01T10:00:00Z", output=10)) + "\n"
        "not-valid-json\n"
        "{also not valid\n"
    )

    usage, _, _, malformed = read_usage(projects_dir=tmp_path)
    assert malformed == 2
    assert usage["claude-sonnet-4-6"].output_tokens == 10


def test_multiple_models(tmp_path):
    _write_session(tmp_path, "proj-a", "session-1", [
        _assistant("claude-sonnet-4-6", "2026-06-01T10:00:00Z", output=50),
        _assistant("claude-opus-4-8", "2026-06-01T11:00:00Z", output=100),
    ])

    usage, _, _, _ = read_usage(projects_dir=tmp_path)
    assert usage["claude-sonnet-4-6"].output_tokens == 50
    assert usage["claude-opus-4-8"].output_tokens == 100


def test_session_count_is_unique_across_projects(tmp_path):
    # Two files with the same stem in different projects = 2 sessions
    _write_session(tmp_path, "proj-a", "abc123",
                   [_assistant("claude-sonnet-4-6", "2026-06-01T10:00:00Z", output=10)])
    _write_session(tmp_path, "proj-b", "abc123",
                   [_assistant("claude-sonnet-4-6", "2026-06-01T11:00:00Z", output=10)])

    _, _, sessions, _ = read_usage(projects_dir=tmp_path)
    assert sessions == 2


def test_fallback_to_unknown_model(tmp_path):
    session_dir = tmp_path / "proj-a"
    session_dir.mkdir(parents=True)
    record = {
        "type": "assistant",
        "timestamp": "2026-06-01T10:00:00Z",
        "message": {
            "usage": {
                "input_tokens": 10,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "output_tokens": 5,
            }
        },
    }
    (session_dir / "session.jsonl").write_text(json.dumps(record))

    usage, _, _, _ = read_usage(projects_dir=tmp_path)
    assert "unknown" in usage
    assert usage["unknown"].output_tokens == 5
