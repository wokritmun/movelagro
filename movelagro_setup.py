"""
movelagro_setup.py — Run this once to create the entire MovelAgro project.

Usage:
    python3 movelagro_setup.py
    
This creates a ./movelagro/ directory with all files in place.
"""
import os, textwrap

ROOT = os.path.join(os.getcwd(), "movelagro")

FILES = {}

# ── config.py ────────────────────────────────────────────────────────────────
FILES["config.py"] = """
CROP = "irish_potato"
CERTIFICATION_AUTHORITY_NAME = "NRCRI"
GEOGRAPHY = "Jos Plateau, Nigeria"
SEASON_STRUCTURE = ["wet", "dry"]
DELIVERY_RELIABILITY_THRESHOLD = 0.85
NODE_ID_FORMAT = "{iso_country}-{lga_code}-{year}-{sequence:04d}"
ISO_COUNTRY = "NGA"
DEFAULT_AVG_YIELD_KG_PER_HA = 12_000.0

import os
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://movelagro:movelagro@localhost/movelagro"
)
"""

# ── database.py ───────────────────────────────────────────────────────────────
FILES["database.py"] = """
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from config import DATABASE_URL

class Base(DeclarativeBase):
    pass

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
"""

# ── models/__init__.py ────────────────────────────────────────────────────────
FILES["models/__init__.py"] = """
from .authority import CertificationAuthority
from .node import Node
from .report import SeasonalReport
from .demand import DemandSignal
from .reconciliation import ReconciliationResult
from .audit import AuditEntry

__all__ = ["CertificationAuthority","Node","SeasonalReport","DemandSignal","ReconciliationResult","AuditEntry"]
"""

# ── models/authority.py ───────────────────────────────────────────────────────
FILES["models/authority.py"] = """
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel
from database import Base

class CertificationAuthority(Base):
    __tablename__ = "certification_authorities"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class AuthorityCreate(BaseModel):
    name: str
    active: bool = True

class AuthorityRead(BaseModel):
    id: int
    name: str
    active: bool
    created_at: datetime
    model_config = {"from_attributes": True}
"""

# ── models/node.py ────────────────────────────────────────────────────────────
FILES["models/node.py"] = """
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Boolean, Float, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel
from database import Base

class Node(Base):
    __tablename__ = "nodes"
    node_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    farmer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    certification_authority_id: Mapped[int] = mapped_column(Integer, ForeignKey("certification_authorities.id"), nullable=False)
    certification_event_id: Mapped[str] = mapped_column(String(100), nullable=False)
    seed_lot_id: Mapped[str] = mapped_column(String(100), nullable=False)
    lga_code: Mapped[str] = mapped_column(String(20), nullable=False)
    gps_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hectares: Mapped[float] = mapped_column(Float, nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class NodeRegisterRequest(BaseModel):
    farmer_name: str
    phone: Optional[str] = None
    certification_authority_id: int
    certification_event_id: str
    seed_lot_id: str
    lga_code: str
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    hectares: float

class NodeRead(BaseModel):
    node_id: str
    farmer_name: str
    phone: Optional[str]
    verified: bool
    certification_authority_id: int
    certification_event_id: str
    seed_lot_id: str
    lga_code: str
    gps_lat: Optional[float]
    gps_lon: Optional[float]
    hectares: float
    registered_at: datetime
    model_config = {"from_attributes": True}

class NodeRegisterResponse(BaseModel):
    node_id: str
    qr_payload: str
    message: str
"""

# ── models/report.py ──────────────────────────────────────────────────────────
FILES["models/report.py"] = """
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Float, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel
from database import Base

class SeasonalReport(Base):
    __tablename__ = "seasonal_reports"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(String(50), ForeignKey("nodes.node_id"), nullable=False)
    season: Mapped[str] = mapped_column(String(20), nullable=False)
    promised_delivery_kg: Mapped[float] = mapped_column(Float, nullable=False)
    actual_delivery_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yield_kg_per_hectare: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    @property
    def delivery_reliability(self) -> Optional[float]:
        if self.actual_delivery_kg is None:
            return None
        if self.promised_delivery_kg == 0:
            return 0.0
        return self.actual_delivery_kg / self.promised_delivery_kg

class ReportSubmitRequest(BaseModel):
    season: str
    promised_delivery_kg: float
    actual_delivery_kg: Optional[float] = None
    yield_kg_per_hectare: Optional[float] = None

class ReportRead(BaseModel):
    id: int
    node_id: str
    season: str
    promised_delivery_kg: float
    actual_delivery_kg: Optional[float]
    yield_kg_per_hectare: Optional[float]
    delivery_reliability: Optional[float] = None
    submitted_at: datetime
    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_reliability(cls, report) -> "ReportRead":
        obj = cls.model_validate(report)
        obj.delivery_reliability = report.delivery_reliability
        return obj

class NodeHistoryResponse(BaseModel):
    node_id: str
    reports: list[ReportRead]
    avg_yield_kg_per_ha: Optional[float]
    avg_delivery_reliability: Optional[float]
"""

# ── models/demand.py ──────────────────────────────────────────────────────────
FILES["models/demand.py"] = """
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel
from database import Base

class DemandSignal(Base):
    __tablename__ = "demand_signals"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    manufacturer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    crop: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity_kg: Mapped[float] = mapped_column(Float, nullable=False)
    target_season: Mapped[str] = mapped_column(String(20), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class DemandSignalCreate(BaseModel):
    manufacturer_id: str
    crop: str
    quantity_kg: float
    target_season: str

class DemandSignalRead(BaseModel):
    id: int
    manufacturer_id: str
    crop: str
    quantity_kg: float
    target_season: str
    received_at: datetime
    model_config = {"from_attributes": True}
"""

# ── models/reconciliation.py ──────────────────────────────────────────────────
FILES["models/reconciliation.py"] = """
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Float, DateTime, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel
from database import Base

class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    demand_signal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    demand_kg: Mapped[float] = mapped_column(Float, nullable=False)
    verified_supply_kg: Mapped[float] = mapped_column(Float, nullable=False)
    gap_kg: Mapped[float] = mapped_column(Float, nullable=False)
    coverage_status: Mapped[str] = mapped_column(String(20), nullable=False)
    hectares_needed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nodes_eligible: Mapped[int] = mapped_column(Integer, nullable=False)
    nodes_excluded_reliability: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_enrollments: Mapped[int] = mapped_column(Integer, nullable=False)
    top_nodes_by_lga: Mapped[dict] = mapped_column(JSON, nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ReconciliationResultRead(BaseModel):
    id: int
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
    run_at: datetime
    model_config = {"from_attributes": True}
"""

# ── models/audit.py ───────────────────────────────────────────────────────────
FILES["models/audit.py"] = """
from datetime import datetime, timezone
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel
from database import Base

class AuditEntry(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    record_id: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)

class AuditEntryRead(BaseModel):
    id: int
    event_type: str
    timestamp: datetime
    record_id: str
    payload_hash: str
    previous_hash: str
    model_config = {"from_attributes": True}
"""

# ── core/__init__.py ──────────────────────────────────────────────────────────
FILES["core/__init__.py"] = """
from .id_generator import generate_node_id
from .audit_chain import append_audit_entry
from .reconciliation_engine import run_reconciliation

__all__ = ["generate_node_id", "append_audit_entry", "run_reconciliation"]
"""

# ── core/id_generator.py ──────────────────────────────────────────────────────
FILES["core/id_generator.py"] = """
from config import ISO_COUNTRY
from sqlalchemy import text

async def generate_node_id(session, lga_code: str, year: int) -> str:
    result = await session.execute(
        text("SELECT COUNT(*) FROM nodes WHERE lga_code = :lga AND node_id LIKE :prefix"),
        {"lga": lga_code, "prefix": f"{ISO_COUNTRY}-{lga_code}-{year}-%"},
    )
    count = result.scalar() or 0
    return f"{ISO_COUNTRY}-{lga_code}-{year}-{count + 1:04d}"
"""

# ── core/audit_chain.py ───────────────────────────────────────────────────────
FILES["core/audit_chain.py"] = """
import hashlib, json
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.audit import AuditEntry

async def append_audit_entry(session: AsyncSession, event_type: str, record_id: str, payload: dict) -> AuditEntry:
    result = await session.execute(select(AuditEntry).order_by(AuditEntry.id.desc()).limit(1))
    latest = result.scalars().first()
    previous_hash = latest.payload_hash if latest else "GENESIS"
    canonical = json.dumps(payload, sort_keys=True, default=str)
    payload_hash = hashlib.sha256(canonical.encode()).hexdigest()
    entry = AuditEntry(
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        record_id=str(record_id),
        payload_hash=payload_hash,
        previous_hash=previous_hash,
    )
    session.add(entry)
    return entry

async def verify_chain(session: AsyncSession) -> tuple[bool, str]:
    result = await session.execute(select(AuditEntry).order_by(AuditEntry.id.asc()))
    entries = result.scalars().all()
    prev_hash = "GENESIS"
    for entry in entries:
        if entry.previous_hash != prev_hash:
            return False, f"Chain broken at entry {entry.id}"
        prev_hash = entry.payload_hash
    return True, "OK"
"""

# ── core/reconciliation_engine.py ────────────────────────────────────────────
FILES["core/reconciliation_engine.py"] = """
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
"""

# ── api/__init__.py ───────────────────────────────────────────────────────────
FILES["api/__init__.py"] = """
from .registration import router as registration_router
from .reporting import router as reporting_router
from .reconciliation import router as reconciliation_router

__all__ = ["registration_router", "reporting_router", "reconciliation_router"]
"""

# ── api/registration.py ───────────────────────────────────────────────────────
FILES["api/registration.py"] = """
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_session
from models.authority import CertificationAuthority
from models.node import Node, NodeRegisterRequest, NodeRegisterResponse
from core.id_generator import generate_node_id
from core.audit_chain import append_audit_entry

router = APIRouter(prefix="/nodes", tags=["Registration"])

@router.post("/register", response_model=NodeRegisterResponse, status_code=201)
async def register_node(body: NodeRegisterRequest, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(CertificationAuthority).where(CertificationAuthority.id == body.certification_authority_id))
    authority = result.scalars().first()
    if authority is None:
        raise HTTPException(status_code=422, detail=f"CertificationAuthority id={body.certification_authority_id} does not exist.")
    if not authority.active:
        raise HTTPException(status_code=422, detail=f"CertificationAuthority '{authority.name}' is not active.")

    year = datetime.now(timezone.utc).year
    node_id = await generate_node_id(session, body.lga_code, year)

    node = Node(
        node_id=node_id, farmer_name=body.farmer_name, phone=body.phone,
        verified=True, certification_authority_id=body.certification_authority_id,
        certification_event_id=body.certification_event_id, seed_lot_id=body.seed_lot_id,
        lga_code=body.lga_code, gps_lat=body.gps_lat, gps_lon=body.gps_lon, hectares=body.hectares,
    )
    session.add(node)

    await append_audit_entry(session, "node_registered", node_id, {
        "node_id": node_id, "farmer_name": body.farmer_name,
        "certification_authority_id": body.certification_authority_id,
        "certification_event_id": body.certification_event_id,
        "seed_lot_id": body.seed_lot_id, "lga_code": body.lga_code, "hectares": body.hectares,
    })
    await session.commit()

    qr_payload = json.dumps({"node_id": node_id, "authority": authority.name,
        "event": body.certification_event_id, "lot": body.seed_lot_id, "ha": body.hectares}, separators=(",", ":"))

    return NodeRegisterResponse(node_id=node_id, qr_payload=qr_payload,
        message=f"Node {node_id} registered and verified by {authority.name}.")
"""

# ── api/reporting.py ──────────────────────────────────────────────────────────
FILES["api/reporting.py"] = """
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
"""

# ── api/reconciliation.py ─────────────────────────────────────────────────────
FILES["api/reconciliation.py"] = """
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
"""

# ── main.py ───────────────────────────────────────────────────────────────────
FILES["main.py"] = """
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from database import engine, AsyncSessionLocal, Base
from api import registration_router, reporting_router, reconciliation_router
from core.audit_chain import verify_chain

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="MovelAgro Verified Supply Protocol", version="1.0.0", lifespan=lifespan)
app.include_router(registration_router)
app.include_router(reporting_router)
app.include_router(reconciliation_router)

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    return '<html><body style="font-family:monospace;padding:2rem"><h2>MovelAgro</h2><a href="/docs">API docs</a> | <a href="/audit/chain-check">Audit chain</a></body></html>'

@app.get("/audit/chain-check", tags=["Audit"])
async def check_audit_chain():
    async with AsyncSessionLocal() as session:
        ok, message = await verify_chain(session)
    return {"chain_intact": ok, "message": message}
"""

# ── seed_data/generate.py ─────────────────────────────────────────────────────
FILES["seed_data/__init__.py"] = ""
FILES["seed_data/generate.py"] = """
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from config import DATABASE_URL
from database import Base
from models import CertificationAuthority, Node, SeasonalReport
from core.audit_chain import append_audit_entry

LGAS = [{"code": "PLT"}, {"code": "JOS"}, {"code": "BKS"}]

FARMERS = [
    ("Amos Dung",       0, 2.5,  9.887, 8.890), ("Miriam Fwa",      0, 1.8,  9.901, 8.872),
    ("Sunday Gyang",    0, 3.2,  9.875, 8.910), ("Rebecca Nden",    0, 2.0,  9.862, 8.855),
    ("Joseph Pam",      0, 4.1,  9.920, 8.899), ("Grace Lot",       0, 1.5,  9.845, 8.878),
    ("Daniel Musa",     1, 2.8,  9.944, 8.943), ("Esther Lalong",   1, 3.5,  9.930, 8.957),
    ("Peter Dashe",     1, 2.2,  9.958, 8.921), ("Patience Pwol",   1, 1.9,  9.971, 8.935),
    ("Emmanuel Rindam", 1, 2.6,  9.915, 8.964), ("Naomi Bulus",     1, 3.0,  9.939, 8.978),
    ("Moses Chollom",   2, 1.7,  9.780, 8.970), ("Ruth Lar",        2, 2.3,  9.795, 8.988),
    ("Isaac Wuyep",     2, 3.8,  9.768, 9.002), ("Deborah Gwerzo",  2, 2.1,  9.812, 8.961),
    ("Abel Zang",       2, 2.9,  9.756, 8.975), ("Lydia Fom",       2, 1.6,  9.801, 8.993),
    ("Nathan Gyong",    2, 3.3,  9.773, 9.015), ("Comfort Kwom",    2, 2.0,  9.830, 8.950),
]

SEASON_DATA = {
    0:  [("2023-wet",28000,27200,10880),("2023-dry",14000,13800,5520),("2024-wet",30000,29700,11880)],
    1:  [("2023-wet",19800,19400,10778),("2023-dry",10000, 9900,5500),("2024-wet",21600,21200,11778)],
    2:  [("2023-wet",36000,35500,11094),("2023-dry",18000,17800,5563),("2024-wet",38400,38100,11906)],
    3:  [("2023-wet",22400,16128, 8064),("2023-dry",11200, 8064,4032),("2024-wet",24000,17280, 8640)],
    4:  [("2023-wet",45000,44000,10732),("2023-dry",22500,22000,5366),("2024-wet",49200,48500,11829)],
    5:  [("2023-wet",16800,16400,10933),("2023-dry", 8400, 8200,5467),("2024-wet",18000,17600,11733)],
    6:  [("2023-wet",31200,28000,10000),("2023-dry",15600,14000,5000),("2024-wet",33600,30240,10800)],
    7:  [("2023-wet",39000,38700,11057),("2023-dry",19500,19200,5486),("2024-wet",42000,41700,11914)],
    8:  [("2023-wet",24200,23800,10818),("2023-dry",12100,11900,5409),("2024-wet",26400,26000,11818)],
    9:  [("2023-wet",21000,20700,10895),("2023-dry",10500,10300,5421),("2024-wet",22800,22600,11895)],
    10: [("2023-wet",28600,27300,10500),("2023-dry",14300,13600,5231),("2024-wet",31200,29800,11462)],
    11: [("2023-wet",33000,32600,10867),("2023-dry",16500,16200,5400),("2024-wet",36000,35600,11867)],
    12: [("2023-wet",18700,13500, 7941),("2023-dry", 9350, 6750,3971),("2024-wet",20400,14700, 8647)],
    13: [("2023-wet",25300,25000,10870),("2023-dry",12650,12400,5391),("2024-wet",27600,27200,11826)],
    14: [("2023-wet",42000,41500,10921),("2023-dry",21000,20700,5447),("2024-wet",45600,45100,11868)],
    15: [("2023-wet",23100,22700,10810),("2023-dry",11550,11300,5381),("2024-wet",25200,24900,11857)],
    16: [("2023-wet",32000,31600,10897),("2023-dry",16000,15700,5414),("2024-wet",34800,34500,11897)],
    17: [("2023-wet",17600,17300,10813),("2023-dry", 8800, 8600,5375),("2024-wet",19200,18900,11813)],
    18: [("2023-wet",36300,35900,10879),("2023-dry",18150,17900,5424),("2024-wet",39600,39200,11879)],
    19: [("2023-wet",22000,21700,10850),("2023-dry",11000,10800,5400),("2024-wet",24000,23700,11850)],
}

async def seed(session):
    existing = await session.execute(select(CertificationAuthority))
    if existing.scalars().first():
        print("Seed data already present — skipping.")
        return

    print("Seeding MovelAgro database...")
    authority = CertificationAuthority(name="NRCRI", active=True)
    session.add(authority)
    await session.flush()
    print(f"  ✓ CertificationAuthority: NRCRI (id={authority.id})")

    node_ids = []
    counters = {}
    base_time = datetime(2023, 1, 15, 8, 0, 0, tzinfo=timezone.utc)

    for i, (name, lga_idx, ha, lat, lon) in enumerate(FARMERS):
        lga_code = LGAS[lga_idx]["code"]
        counters[lga_code] = counters.get(lga_code, 0) + 1
        node_id = f"NGA-{lga_code}-2023-{counters[lga_code]:04d}"
        node = Node(
            node_id=node_id, farmer_name=name, phone=f"+234-80{i:02d}-000-000",
            verified=True, certification_authority_id=authority.id,
            certification_event_id=f"NRCRI-SEED-DIST-2023-PLT-{i+1:03d}",
            seed_lot_id=f"SL-2023-CIP-{i+1:04d}", lga_code=lga_code,
            gps_lat=lat, gps_lon=lon, hectares=ha,
            registered_at=base_time + timedelta(hours=i*2),
        )
        session.add(node)
        await session.flush()
        node_ids.append(node_id)
        await append_audit_entry(session, "node_registered", node_id,
            {"node_id": node_id, "farmer_name": name, "lga_code": lga_code})

    print(f"  ✓ {len(node_ids)} nodes registered")

    season_offsets = {"2023-wet": timedelta(days=180), "2023-dry": timedelta(days=365), "2024-wet": timedelta(days=545)}
    report_count = 0
    for i, node_id in enumerate(node_ids):
        for season, promised, actual, yld in SEASON_DATA[i]:
            r = SeasonalReport(node_id=node_id, season=season, promised_delivery_kg=float(promised),
                actual_delivery_kg=float(actual), yield_kg_per_hectare=float(yld),
                submitted_at=base_time + season_offsets[season] + timedelta(hours=i))
            session.add(r)
            await session.flush()
            await append_audit_entry(session, "report_submitted", node_id,
                {"node_id": node_id, "season": season, "actual_kg": actual})
            report_count += 1

    print(f"  ✓ {report_count} seasonal reports submitted")

    ghost = Node(node_id="NGA-PLT-2024-9999", farmer_name="Ghost Farmer (unverified)",
        verified=False, certification_authority_id=authority.id,
        certification_event_id="NONE", seed_lot_id="NONE", lga_code="PLT", hectares=2.0)
    session.add(ghost)

    await session.commit()
    print("  ✓ Unverified ghost node added (NGA-PLT-2024-9999) — for rejection demo")
    print("\\nSeed complete. Try: POST /reconciliation/run")

async def main():
    db_url = os.environ.get("DATABASE_URL", DATABASE_URL)
    eng = create_async_engine(db_url, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        await seed(session)
    await eng.dispose()

if __name__ == "__main__":
    asyncio.run(main())
"""

# ── tests/ ────────────────────────────────────────────────────────────────────
FILES["tests/__init__.py"] = ""
FILES["pytest.ini"] = "[pytest]\nasyncio_mode = auto\ntestpaths = tests\n"
FILES["requirements.txt"] = (
    "fastapi==0.115.0\nuvicorn[standard]==0.30.6\n"
    "sqlalchemy[asyncio]==2.0.35\nasyncpg==0.29.0\n"
    "pydantic==2.9.2\nhttpx==0.27.2\n"
    "pytest==8.3.3\npytest-asyncio==0.24.0\nanyio==4.6.0\n"
)

FILES["Dockerfile"] = (
    "FROM python:3.12-slim\nWORKDIR /app\n"
    "COPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\n"
    "COPY . .\nEXPOSE 8000\n"
)

# ── Write everything ──────────────────────────────────────────────────────────

created = 0
for rel_path, content in FILES.items():
    full_path = os.path.join(ROOT, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write(textwrap.dedent(content).lstrip("\n"))
    created += 1

print(f"\nMovelAgro project created at: {ROOT}")
print(f"{created} files written.\n")
print("Next steps:")
print("  cd movelagro")
print("  python3 -m venv .venv && source .venv/bin/activate")
print("  pip install -r requirements.txt")
print("  createdb movelagro")
print(f"  export DATABASE_URL='postgresql+asyncpg://$(whoami)@localhost/movelagro'")
print("  python3 seed_data/generate.py")
print("  uvicorn main:app --reload")
print("\nThen open: http://localhost:8000/docs")
