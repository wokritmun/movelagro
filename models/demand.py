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
