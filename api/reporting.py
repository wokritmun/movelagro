from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_session
from models.node import Node
from models.report import SeasonalReport, ReportSubmitRequest, ReportRead, NodeHistoryResponse
from core.audit_chain import append_audit_entry
from config import SEASON_STRUCTURE

router = APIRouter(prefix="/nodes", tags=["Reporting"])

@router.post("/{node_id}/report", response_model=ReportRead, status_code=201)
async def submit_report(node_id: str, body: ReportSubmitRequest, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Node).where(Node.node_id == node_id))
    node = result.scalars().first()
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found.")
    if not node.verified:
        raise HTTPException(status_code=403, detail=(
            f"Node {node_id} has no verified certification event. "
            "Data cannot be accepted into the protocol before identity is established."
        ))
    parts = body.season.split("-")
    if len(parts) != 2 or not parts[0].isdigit() or parts[1] not in SEASON_STRUCTURE:
        raise HTTPException(status_code=422, detail=f"Invalid season '{body.season}'. Expected '<year>-<wet|dry>'.")

    report = SeasonalReport(node_id=node_id, season=body.season,
        promised_delivery_kg=body.promised_delivery_kg,
        actual_delivery_kg=body.actual_delivery_kg,
        yield_kg_per_hectare=body.yield_kg_per_hectare)
    session.add(report)
    await append_audit_entry(session, "report_submitted", node_id, {
        "node_id": node_id, "season": body.season,
        "promised_delivery_kg": body.promised_delivery_kg,
        "actual_delivery_kg": body.actual_delivery_kg,
    })
    await session.commit()
    await session.refresh(report)
    return ReportRead.from_orm_with_reliability(report)

@router.get("/{node_id}/history", response_model=NodeHistoryResponse)
async def get_node_history(node_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Node).where(Node.node_id == node_id))
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found.")
    result = await session.execute(select(SeasonalReport).where(SeasonalReport.node_id == node_id).order_by(SeasonalReport.submitted_at.asc()))
    reports = result.scalars().all()
    report_reads = [ReportRead.from_orm_with_reliability(r) for r in reports]
    completed = [r for r in reports if r.actual_delivery_kg is not None]
    avg_yield, avg_reliability = None, None
    if completed:
        yields = [r.yield_kg_per_hectare for r in completed if r.yield_kg_per_hectare]
        rels = [r.delivery_reliability for r in completed if r.delivery_reliability is not None]
        avg_yield = round(sum(yields)/len(yields), 2) if yields else None
        avg_reliability = round(sum(rels)/len(rels), 4) if rels else None
    return NodeHistoryResponse(node_id=node_id, reports=report_reads,
        avg_yield_kg_per_ha=avg_yield, avg_delivery_reliability=avg_reliability)
