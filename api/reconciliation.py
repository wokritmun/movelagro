from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_session
from models.demand import DemandSignal, DemandSignalCreate
from models.node import Node
from models.report import SeasonalReport
from models.reconciliation import ReconciliationResult, ReconciliationResultRead
from core.reconciliation_engine import run_reconciliation, ReconInput, NodeSummary
from core.audit_chain import append_audit_entry
from config import DELIVERY_RELIABILITY_THRESHOLD, DEFAULT_AVG_YIELD_KG_PER_HA

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])

@router.post("/run", response_model=ReconciliationResultRead, status_code=201)
async def run_reconciliation_endpoint(body: DemandSignalCreate, session: AsyncSession = Depends(get_session)):
    demand = DemandSignal(manufacturer_id=body.manufacturer_id, crop=body.crop,
        quantity_kg=body.quantity_kg, target_season=body.target_season)
    session.add(demand)
    await session.flush()

    nodes_result = await session.execute(select(Node).where(Node.verified == True))
    db_nodes = nodes_result.scalars().all()

    node_summaries = []
    for node in db_nodes:
        reports_result = await session.execute(select(SeasonalReport).where(
            SeasonalReport.node_id == node.node_id,
            SeasonalReport.actual_delivery_kg.isnot(None)))
        completed = reports_result.scalars().all()
        if not completed:
            continue
        yields = [r.yield_kg_per_hectare for r in completed if r.yield_kg_per_hectare]
        rels = [r.delivery_reliability for r in completed if r.delivery_reliability is not None]
        avg_yield = (sum(yields)/len(yields)) if yields else DEFAULT_AVG_YIELD_KG_PER_HA
        avg_rel = (sum(rels)/len(rels)) if rels else 0.0
        node_summaries.append(NodeSummary(node_id=node.node_id, lga_code=node.lga_code,
            hectares=node.hectares, avg_yield_kg_per_ha=avg_yield, avg_delivery_reliability=avg_rel))

    output = run_reconciliation(ReconInput(demand_signal_id=demand.id, demand_kg=body.quantity_kg,
        target_season=body.target_season, nodes=node_summaries,
        reliability_threshold=DELIVERY_RELIABILITY_THRESHOLD, avg_yield_kg_per_ha=DEFAULT_AVG_YIELD_KG_PER_HA))

    result_row = ReconciliationResult(demand_signal_id=demand.id, demand_kg=output.demand_kg,
        verified_supply_kg=output.verified_supply_kg, gap_kg=output.gap_kg,
        coverage_status=output.coverage_status, hectares_needed=output.hectares_needed,
        nodes_eligible=output.nodes_eligible, nodes_excluded_reliability=output.nodes_excluded_reliability,
        recommended_enrollments=output.recommended_enrollments, top_nodes_by_lga=output.top_nodes_by_lga)
    session.add(result_row)
    await session.flush()

    await append_audit_entry(session, "reconciliation_run", str(result_row.id), {
        "demand_signal_id": demand.id, "demand_kg": output.demand_kg,
        "verified_supply_kg": output.verified_supply_kg, "gap_kg": output.gap_kg,
        "coverage_status": output.coverage_status})
    await session.commit()
    await session.refresh(result_row)
    return ReconciliationResultRead.model_validate(result_row)

@router.get("/{result_id}", response_model=ReconciliationResultRead)
async def get_result(result_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ReconciliationResult).where(ReconciliationResult.id == result_id))
    row = result.scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Result {result_id} not found.")
    return ReconciliationResultRead.model_validate(row)
