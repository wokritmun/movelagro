"""api/field_ingest.py — Field officer node ingest endpoint.

Accepts the payload produced by field/register.html, verifies the
SHA-256 audit hash, and bridges into the existing node registration
schema. This is the backend counterpart to the offline field form.

Endpoint: POST /api/v1/nodes

The field form constructs an audit hash from the concatenation of all
identity-bearing fields at the moment of GPS capture:

    SHA-256(officerId|certEvent|farmerId|plotId|lotSeal|quantityKg|lat|lng|capturedAt)

This endpoint recomputes the same hash and rejects any record where
it does not match — the tamper-detection guarantee stated in Q6.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models.node import Node
from models.authority import CertificationAuthority
from core.audit_chain import append_audit_entry
from core.id_generator import generate_node_id

router = APIRouter(prefix="/api/v1", tags=["Field Ingest"])


# ── Incoming payload schema (matches field/register.html output) ──────────────

class FieldEventPayload(BaseModel):
    officerId: str
    certEvent: str


class FieldFarmerPayload(BaseModel):
    farmerId: str
    plotId: str


class FieldSeedPayload(BaseModel):
    variety: str
    lotSeal: str
    quantityKg: int


class FieldGPSPayload(BaseModel):
    lat: str
    lng: str
    accuracy: float = 0.0
    capturedAt: int  # Unix ms


class FieldDeviceInfo(BaseModel):
    userAgent: Optional[str] = None
    online: Optional[bool] = None


class FieldSubmission(BaseModel):
    """Raw record produced by the field officer PWA."""
    nodeId: str = Field(..., description="Client-generated NODE-XXXXXXX identifier")
    schemaVersion: str = "1.0"
    syncStatus: str = "pending"
    timestamp: int
    auditHash: str
    event: FieldEventPayload
    farmer: FieldFarmerPayload
    seed: FieldSeedPayload
    gps: FieldGPSPayload
    deviceInfo: Optional[FieldDeviceInfo] = None


# ── Plot metadata lookup ──────────────────────────────────────────────────────

_PLOT_LGA_MAP: dict[str, str] = {
    "PLT-A": "PLT", "PLT-B": "PLT", "PLT-C": "PLT", "PLT-D": "PLT",
    "JOS-A": "JOS", "JOS-B": "JOS",
    "BKS-A": "BKS",
}

_PLOT_HECTARES_MAP: dict[str, float] = {
    "PLT-A": 0.8, "PLT-B": 1.2, "PLT-C": 0.5, "PLT-D": 1.0,
    "JOS-A": 0.9, "JOS-B": 1.1,
    "BKS-A": 0.7,
}


def _compute_expected_hash(submission: FieldSubmission) -> str:
    """Recompute the audit hash using the same algorithm as field/register.html."""
    components = [
        submission.event.officerId,
        submission.event.certEvent,
        submission.farmer.farmerId,
        submission.farmer.plotId,
        submission.seed.lotSeal,
        str(submission.seed.quantityKg),
        submission.gps.lat,
        submission.gps.lng,
        str(submission.gps.capturedAt),
    ]
    return hashlib.sha256("|".join(components).encode("utf-8")).hexdigest()


# ── Response schema ───────────────────────────────────────────────────────────

class FieldIngestResponse(BaseModel):
    node_id: str
    client_node_id: str
    cert_event: str
    farmer_id: str
    lga_code: str
    seed_lot: str
    quantity_kg: int
    gps_lat: float
    gps_lng: float
    registered_at: str
    hash_verified: bool


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post(
    "/nodes",
    response_model=FieldIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a field officer node registration",
)
async def ingest_field_registration(
    submission: FieldSubmission,
    session: AsyncSession = Depends(get_session),
) -> FieldIngestResponse:

    # 1. Verify audit hash
    expected = _compute_expected_hash(submission)
    if submission.auditHash != expected:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "audit_hash_mismatch",
                "message": (
                    "The submitted audit hash does not match the recomputed hash. "
                    "Record rejected — data may have been modified after GPS capture."
                ),
                "client_node_id": submission.nodeId,
            },
        )

    # 2. Resolve active certification authority
    result = await session.execute(
        select(CertificationAuthority).where(CertificationAuthority.active == True).limit(1)
    )
    authority = result.scalar_one_or_none()
    if authority is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No active certification authority registered. Run seed data setup first.",
        )

    # 3. Idempotency — same audit hash already ingested
    existing = await session.execute(
        select(Node).where(Node.field_audit_hash == submission.auditHash)
    )
    existing_node = existing.scalar_one_or_none()
    if existing_node is not None:
        return FieldIngestResponse(
            node_id=existing_node.node_id,
            client_node_id=submission.nodeId,
            cert_event=submission.event.certEvent,
            farmer_id=submission.farmer.farmerId,
            lga_code=existing_node.lga_code,
            seed_lot=submission.seed.lotSeal,
            quantity_kg=submission.seed.quantityKg,
            gps_lat=existing_node.gps_lat,
            gps_lng=existing_node.gps_lon,
            registered_at=existing_node.registered_at.isoformat(),
            hash_verified=True,
        )

    # 4. Resolve plot metadata
    lga_code = _PLOT_LGA_MAP.get(submission.farmer.plotId, "PLT")
    hectares = _PLOT_HECTARES_MAP.get(submission.farmer.plotId, 1.0)

    # 5. Generate node ID
    registered_at = datetime.now(timezone.utc)
    node_id = await generate_node_id(session, lga_code, registered_at.year)

    # 6. Create node
    node = Node(
        node_id=node_id,
        farmer_name=submission.farmer.farmerId,
        phone=None,
        verified=True,
        certification_authority_id=authority.id,
        certification_event_id=submission.event.certEvent,
        seed_lot_id=submission.seed.lotSeal,
        lga_code=lga_code,
        gps_lat=float(submission.gps.lat),
        gps_lon=float(submission.gps.lng),
        hectares=hectares,
        registered_at=registered_at,
        field_audit_hash=submission.auditHash,
        field_client_node_id=submission.nodeId,
        field_officer_id=submission.event.officerId,
    )
    session.add(node)

    # 7. Append to audit chain
    # Actual signature: append_audit_entry(session, event_type, record_id, payload)
    await append_audit_entry(
        session,
        "field_registration",
        node_id,
        {
            "client_node_id": submission.nodeId,
            "cert_event": submission.event.certEvent,
            "officer_id": submission.event.officerId,
            "farmer_id": submission.farmer.farmerId,
            "seed_lot": submission.seed.lotSeal,
            "quantity_kg": submission.seed.quantityKg,
            "gps_lat": submission.gps.lat,
            "gps_lng": submission.gps.lng,
            "audit_hash": submission.auditHash,
            "captured_at_ms": submission.gps.capturedAt,
        },
    )

    await session.commit()

    return FieldIngestResponse(
        node_id=node_id,
        client_node_id=submission.nodeId,
        cert_event=submission.event.certEvent,
        farmer_id=submission.farmer.farmerId,
        lga_code=lga_code,
        seed_lot=submission.seed.lotSeal,
        quantity_kg=submission.seed.quantityKg,
        gps_lat=float(submission.gps.lat),
        gps_lng=float(submission.gps.lng),
        registered_at=registered_at.isoformat(),
        hash_verified=True,
    )
