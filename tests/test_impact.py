from unittest.mock import MagicMock, patch

import pytest

from cceco.impact import EnvironmentalImpact, ImpactRange, compute_impact


def _make_mock_impacts(
    energy=(0.01, 0.02, 0.03),
    gwp=(0.004, 0.008, 0.012),
    wcf=(0.05, 0.10, 0.15),
    adpe=(1e-9, 2e-9, 3e-9),
    pe=(0.1, 0.2, 0.3),
) -> MagicMock:
    mock = MagicMock()
    mock.has_errors = False
    for attr, (mn, mean, mx) in [
        ("energy", energy),
        ("gwp", gwp),
        ("wcf", wcf),
        ("adpe", adpe),
        ("pe", pe),
    ]:
        v = MagicMock()
        v.min, v.mean, v.max = mn, mean, mx
        getattr(mock, attr).value = v
    return mock


def test_returns_impact_for_known_model():
    with patch("cceco.impact.llm_impacts", return_value=_make_mock_impacts()):
        result = compute_impact("claude-sonnet-4-6", 1000)

    assert result is not None
    assert isinstance(result, EnvironmentalImpact)
    assert result.electricity.mean == pytest.approx(0.02)
    assert result.electricity.unit == "kWh"
    assert result.ghg.unit == "kgCO2eq"
    assert result.water.unit == "L"
    assert result.metals.unit == "kgSbeq"
    assert result.fossil_fuels.unit == "MJ"


def test_returns_none_for_unknown_model():
    mock_result = MagicMock()
    mock_result.has_errors = True
    mock_result.energy = None
    with patch("cceco.impact.llm_impacts", return_value=mock_result):
        result = compute_impact("claude-unknown-99", 1000)
    assert result is None


def test_calls_llm_impacts_with_correct_args():
    with patch("cceco.impact.llm_impacts", return_value=_make_mock_impacts()) as mock_fn:
        compute_impact("claude-opus-4-8", 500)

    mock_fn.assert_called_once_with(
        provider="anthropic",
        model_name="claude-opus-4-8",
        output_token_count=500,
        request_latency=None,
    )


def test_impact_range_min_mean_max():
    with patch("cceco.impact.llm_impacts", return_value=_make_mock_impacts(energy=(0.01, 0.02, 0.03))):
        result = compute_impact("claude-sonnet-4-6", 100)

    assert result.electricity.min == pytest.approx(0.01)
    assert result.electricity.mean == pytest.approx(0.02)
    assert result.electricity.max == pytest.approx(0.03)
