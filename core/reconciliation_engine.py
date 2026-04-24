from __future__ import annotations
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional
from config import DELIVERY_RELIABILITY_THRESHOLD, DEFAULT_AVG_YIELD_KG_PER_HA

@dataclass
class NodeSummary:
    node_id: str
    lga_code: str
    hectares: float
    avg_yield_kg_per_ha: float
    avg_delivery_reliability: float

@dataclass
class ReconInput:
    demand_signal_id: int
    demand_kg: float
    target_season: str
    nodes: list[NodeSummary]
    reliability_threshold: float = DELIVERY_RELIABILITY_THRESHOLD
    avg_yield_kg_per_ha: float = DEFAULT_AVG_YIELD_KG_PER_HA

@dataclass
class ReconOutput:
    demand_signal_id: int
    demand_kg: float
    verified_supply_kg: float
    gap_kg: float
    coverage_status: str
    hectares_needed: Optional[float]
    nodes_eligible: int
    nodes_excluded_reliability: int
    recommended_enrollments: int
    top_nodes_by_lga: dict

def run_reconciliation(inp: ReconInput) -> ReconOutput:
    eligible = [n for n in inp.nodes if n.avg_delivery_reliability >= inp.reliability_threshold]
    nodes_excluded = len(inp.nodes) - len(eligible)
    verified_supply_kg = sum(n.hectares * n.avg_yield_kg_per_ha for n in eligible)
    gap_kg = inp.demand_kg - verified_supply_kg

    if gap_kg <= 0:
        coverage_status = "surplus" if gap_kg < 0 else "covered"
        hectares_needed = None
        recommended_enrollments = 0
    else:
        coverage_status = "shortfall"
        hectares_needed = math.ceil(gap_kg / inp.avg_yield_kg_per_ha)
        avg_ha = (sum(n.hectares for n in eligible) / len(eligible)) if eligible else 1.0
        recommended_enrollments = math.ceil(hectares_needed / avg_ha) if avg_ha > 0 else 0

    by_lga: dict[str, list[str]] = defaultdict(list)
    for n in sorted(eligible, key=lambda x: x.avg_delivery_reliability, reverse=True):
        by_lga[n.lga_code].append(n.node_id)

    return ReconOutput(
        demand_signal_id=inp.demand_signal_id,
        demand_kg=inp.demand_kg,
        verified_supply_kg=round(verified_supply_kg, 2),
        gap_kg=round(gap_kg, 2),
        coverage_status=coverage_status,
        hectares_needed=hectares_needed,
        nodes_eligible=len(eligible),
        nodes_excluded_reliability=nodes_excluded,
        recommended_enrollments=recommended_enrollments,
        top_nodes_by_lga=dict(by_lga),
    )
