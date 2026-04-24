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
