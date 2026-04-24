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
