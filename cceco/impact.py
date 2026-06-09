from __future__ import annotations

from dataclasses import dataclass

from ecologits.tracers.utils import llm_impacts


@dataclass
class ImpactRange:
    min: float
    mean: float
    max: float
    unit: str


@dataclass
class EnvironmentalImpact:
    electricity: ImpactRange
    ghg: ImpactRange
    water: ImpactRange
    metals: ImpactRange
    fossil_fuels: ImpactRange


def compute_impact(model_name: str, output_token_count: int) -> EnvironmentalImpact | None:
    """Return environmental impact for a model, or None if the model is unrecognized."""
    try:
        impacts = llm_impacts(
            provider="anthropic",
            model_name=model_name,
            output_token_count=output_token_count,
            request_latency=None,
        )
    except Exception:
        return None

    if (
        impacts.has_errors
        or impacts.energy is None
        or impacts.gwp is None
        or impacts.wcf is None
        or impacts.adpe is None
        or impacts.pe is None
    ):
        return None

    def _r(v, unit: str) -> ImpactRange:
        return ImpactRange(min=v.min, mean=v.mean, max=v.max, unit=unit)

    return EnvironmentalImpact(
        electricity=_r(impacts.energy.value, "kWh"),
        ghg=_r(impacts.gwp.value, "kgCO2eq"),
        water=_r(impacts.wcf.value, "L"),
        metals=_r(impacts.adpe.value, "kgSbeq"),
        fossil_fuels=_r(impacts.pe.value, "MJ"),
    )
