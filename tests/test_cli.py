import sys
from datetime import date
from unittest.mock import patch

import pytest

from cceco.cli import main
from cceco.impact import EnvironmentalImpact, ImpactRange
from cceco.reader import ModelUsage


def _make_impact() -> EnvironmentalImpact:
    def r(mn, m, mx, u):
        return ImpactRange(min=mn, mean=m, max=mx, unit=u)
    return EnvironmentalImpact(
        electricity=r(0.01, 0.02, 0.03, "kWh"),
        ghg=r(0.004, 0.008, 0.012, "kgCO2eq"),
        water=r(0.05, 0.10, 0.15, "L"),
        metals=r(1e-9, 2e-9, 3e-9, "kgSbeq"),
        fossil_fuels=r(0.1, 0.2, 0.3, "MJ"),
    )


def _make_usage() -> dict:
    u = ModelUsage(
        input_tokens=1000,
        cache_creation_input_tokens=200,
        cache_read_input_tokens=300,
        output_tokens=500,
        request_count=5,
    )
    return {"claude-sonnet-4-6": u}


def test_no_data_prints_message_and_exits(capsys):
    with (
        patch("cceco.cli.read_usage", return_value=({}, 0, 0, 0)),
        patch("sys.argv", ["cceco"]),
        pytest.raises(SystemExit) as exc,
    ):
        main()
    assert exc.value.code == 0
    assert "No Claude Code session data found" in capsys.readouterr().out


def test_no_data_with_date_filter_prints_period_message(capsys):
    with (
        patch("cceco.cli.read_usage", return_value=({}, 0, 0, 0)),
        patch("sys.argv", ["cceco", "--since", "2026-06-01"]),
        pytest.raises(SystemExit) as exc,
    ):
        main()
    assert exc.value.code == 0
    assert "No sessions found in the specified period" in capsys.readouterr().out


def test_outputs_header(capsys):
    with (
        patch("cceco.cli.read_usage", return_value=(_make_usage(), 1, 2, 0)),
        patch("cceco.cli.compute_impact", return_value=_make_impact()),
        patch("sys.argv", ["cceco"]),
    ):
        main()
    out = capsys.readouterr().out
    assert "Claude Code Environmental Impact" in out
    assert "all time" in out
    assert "1 projects" in out
    assert "2 sessions" in out
    assert "5 requests" in out


def test_outputs_token_counts(capsys):
    with (
        patch("cceco.cli.read_usage", return_value=(_make_usage(), 1, 1, 0)),
        patch("cceco.cli.compute_impact", return_value=_make_impact()),
        patch("sys.argv", ["cceco"]),
    ):
        main()
    out = capsys.readouterr().out
    assert "1,000" in out  # input_tokens formatted with comma
    assert "500" in out    # output_tokens


def test_compute_impact_receives_effective_token_count():
    # effective = input(1000) + cache_creation(200) + output(500) = 1700
    # cache_read(300) is excluded — cheap KV-cache lookup, not a forward pass
    with (
        patch("cceco.cli.read_usage", return_value=(_make_usage(), 1, 1, 0)),
        patch("cceco.cli.compute_impact", return_value=_make_impact()) as mock_impact,
        patch("sys.argv", ["cceco"]),
    ):
        main()
    mock_impact.assert_called_once_with("claude-sonnet-4-6", 1700)


def test_outputs_all_five_metrics(capsys):
    with (
        patch("cceco.cli.read_usage", return_value=(_make_usage(), 1, 1, 0)),
        patch("cceco.cli.compute_impact", return_value=_make_impact()),
        patch("sys.argv", ["cceco"]),
    ):
        main()
    out = capsys.readouterr().out
    assert "Electricity" in out
    assert "GHG" in out
    assert "Water" in out
    assert "Abiotic depl." in out
    assert "Fossil fuels" in out


def test_unknown_model_shows_warning(capsys):
    with (
        patch("cceco.cli.read_usage", return_value=(_make_usage(), 1, 1, 0)),
        patch("cceco.cli.compute_impact", return_value=None),
        patch("sys.argv", ["cceco"]),
    ):
        main()
    assert "not recognized by ecologits" in capsys.readouterr().out


def test_malformed_count_shown(capsys):
    with (
        patch("cceco.cli.read_usage", return_value=(_make_usage(), 1, 1, 3)),
        patch("cceco.cli.compute_impact", return_value=_make_impact()),
        patch("sys.argv", ["cceco"]),
    ):
        main()
    assert "Skipped 3 malformed records" in capsys.readouterr().out


def test_since_date_passed_to_reader():
    with (
        patch("cceco.cli.read_usage", return_value=({}, 0, 0, 0)) as mock_read,
        patch("sys.argv", ["cceco", "--since", "2026-06-01"]),
        pytest.raises(SystemExit),
    ):
        main()
    mock_read.assert_called_once_with(since=date(2026, 6, 1), until=None)


def test_until_date_passed_to_reader():
    with (
        patch("cceco.cli.read_usage", return_value=({}, 0, 0, 0)) as mock_read,
        patch("sys.argv", ["cceco", "--until", "2026-06-09"]),
        pytest.raises(SystemExit),
    ):
        main()
    mock_read.assert_called_once_with(since=None, until=date(2026, 6, 9))


def test_invalid_date_exits_with_error(capsys):
    with (
        patch("sys.argv", ["cceco", "--since", "not-a-date"]),
        pytest.raises(SystemExit) as exc,
    ):
        main()
    assert exc.value.code == 1
    assert "Expected YYYY-MM-DD" in capsys.readouterr().out


def test_total_shown_for_multiple_models(capsys):
    usage = {
        "claude-sonnet-4-6": ModelUsage(input_tokens=100, output_tokens=50, request_count=1),
        "claude-opus-4-8": ModelUsage(input_tokens=200, output_tokens=100, request_count=2),
    }
    with (
        patch("cceco.cli.read_usage", return_value=(usage, 1, 1, 0)),
        patch("cceco.cli.compute_impact", return_value=_make_impact()),
        patch("sys.argv", ["cceco"]),
    ):
        main()
    assert "TOTAL" in capsys.readouterr().out


def test_no_total_for_single_model(capsys):
    with (
        patch("cceco.cli.read_usage", return_value=(_make_usage(), 1, 1, 0)),
        patch("cceco.cli.compute_impact", return_value=_make_impact()),
        patch("sys.argv", ["cceco"]),
    ):
        main()
    assert "TOTAL" not in capsys.readouterr().out


def test_period_label_since_only(capsys):
    with (
        patch("cceco.cli.read_usage", return_value=(_make_usage(), 1, 1, 0)),
        patch("cceco.cli.compute_impact", return_value=_make_impact()),
        patch("sys.argv", ["cceco", "--since", "2026-06-01"]),
    ):
        main()
    assert "since 2026-06-01" in capsys.readouterr().out


def test_period_label_since_and_until(capsys):
    with (
        patch("cceco.cli.read_usage", return_value=(_make_usage(), 1, 1, 0)),
        patch("cceco.cli.compute_impact", return_value=_make_impact()),
        patch("sys.argv", ["cceco", "--since", "2026-06-01", "--until", "2026-06-09"]),
    ):
        main()
    assert "2026-06-01 to 2026-06-09" in capsys.readouterr().out
