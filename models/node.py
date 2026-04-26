from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Boolean, Float, DateTime, ForeignKey, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel
from database import Base


class Node(Base):
    __tablename__ = "nodes"

    node_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    farmer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    certification_authority_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("certification_authorities.id"), nullable=False
    )
    certification_event_id: Mapped[str] = mapped_column(String(100), nullable=False)
    seed_lot_id: Mapped[str] = mapped_column(String(100), nullable=False)
    lga_code: Mapped[str] = mapped_column(String(20), nullable=False)
    gps_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hectares: Mapped[float] = mapped_column(Float, nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # ── Field layer additions ─────────────────────────────────────────────────
    # Populated only for nodes registered via the offline field form.
    # All three are nullable so existing nodes are unaffected.

    field_audit_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    field_client_node_id: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )
    field_officer_id: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )


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
    field_audit_hash: Optional[str] = None
    field_client_node_id: Optional[str] = None
    field_officer_id: Optional[str] = None
    model_config = {"from_attributes": True}


class NodeRegisterResponse(BaseModel):
    node_id: str
    qr_payload: str
    message: str
