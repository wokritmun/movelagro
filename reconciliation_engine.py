"""core/reconciliation_engine.py — Supply/demand reconciliation logic.

This module is PURE: it accepts data structures and returns results.
No database sessions. No HTTP. Fully unit-testable.

Algorithm:
1. Filter to verified nodes only (trust anchor enforced upstream)
2. Filter to nodes with ≥1 completed seasonal report (actual_delivery_kg set)
3. Filter to nodes meeting the delivery_reliability threshold
4. Sum projected supply capacity (hectares × avg_yield_kg_per_ha)
5. Compute gap vs demand
6. Bucket top nodes by LGA for the enrollment recommendation
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from config import DELIVERY_RELIABILITY_THRESHOLD, DEFAULT_AVG_YIELD_KG_PER_HA


@dataclass
class NodeSummary:
    """Slim projection of what we need from a Node for reconciliation."""
    node_id: str
    lga_code: str
    hectares: float
    avg_yield_kg_per_ha: float
    avg_delivery_reliability: float


@dataclass
class ReconInput:
    """All data the engine needs — passed in by the API layer."""
    demand_signal_id: int
    demand_kg: float
    target_season: str
    nodes: list[NodeSummary]
    reliability_threshold: float = DELIVERY_RELIABILITY_THRESHOLD
    avg_yield_kg_per_ha: float = DEFAULT_AVG_YIELD_KG_PER_HA  # fallback


@dataclass
class ReconOutput:
    demand_signal_id: int
    demand_kg: float
    verified_supply_kg: float
    gap_kg: float
    coverage_status: str          # "covered" | "shortfall" | "surplus"
    hectares_needed: Optional[float]
    nodes_eligible: int
    nodes_excluded_reliability: int
    recommended_enrollments: int
    top_nodes_by_lga: dict        # {lga_code: [node_id, ...]}


def run_reconciliation(inp: ReconInput) -> ReconOutput:
    """
    Reconcile a demand signal against the verified supply network.
    Returns a structured gap analysis.
    """
    all_nodes = inp.nodes
    total_nodes = len(all_nodes)

    # Step 1 — nodes with ≥1 completed report already filtered before calling engine.
    # Step 2 — filter by reliability threshold.
    eligible = [
        n for n in all_nodes
        if n.avg_delivery_reliability >= inp.reliability_threshold
    ]
    nodes_excluded = total_nodes - len(eligible)

    # Step 3 — sum projected supply (each node's ha × its own avg yield).
    verified_supply_kg = sum(
        n.hectares * n.avg_yield_kg_per_ha for n in eligible
    )

    # Step 4 — gap
    gap_kg = inp.demand_kg - verified_supply_kg

    if gap_kg <= 0:
        coverage_status = "surplus" if gap_kg < 0 else "covered"
        hectares_needed = None
        recommended_enrollments = 0
    else:
        coverage_status = "shortfall"
        # How many more hectares to close the gap?
        hectares_needed = math.ceil(gap_kg / inp.avg_yield_kg_per_ha)
        # Each recommended enrollment = 1 average-sized node (avg hectares of eligible)
        if eligible:
            avg_ha = sum(n.hectares for n in eligible) / len(eligible)
        else:
            avg_ha = 1.0
        recommended_enrollments = math.ceil(hectares_needed / avg_ha) if avg_ha > 0 else 0

    # Step 5 — top nodes by LGA (for the enrollment recommendation)
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
