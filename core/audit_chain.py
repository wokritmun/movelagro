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
