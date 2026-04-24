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
