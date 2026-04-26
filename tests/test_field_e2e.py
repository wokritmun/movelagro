"""tests/test_field_e2e.py — End-to-end integration test.

Tests the full chain without Docker, using an in-memory SQLite database.

Run with:
    pytest tests/test_field_e2e.py -v
"""

from __future__ import annotations

import hashlib
import time
import pytest
import pytest_asyncio

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_session
from main import app

# ── In-memory SQLite override ─────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_session():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_session] = override_get_session


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="module")
async def db_setup():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="module")
async def client(db_setup):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture(scope="module")
async def seeded_authority(db_setup):
    """Insert a CertificationAuthority row.

    The actual model has: id, name, active, created_at.
    No iso_country or geography columns.
    """
    from models.authority import CertificationAuthority
    async with TestSessionLocal() as session:
        authority = CertificationAuthority(
            name="NRCRI",
            active=True,
        )
        session.add(authority)
        await session.commit()
        await session.refresh(authority)
    return authority


# ── Helper ────────────────────────────────────────────────────────────────────

def _build_field_payload(
    farmer_id: str = "FM-0041",
    plot_id: str = "PLT-A",
    lot_seal: str = "LOT-NIC-2025-0088",
    quantity_kg: int = 50,
    officer_id: str = "FO-PNK-001",
    cert_event: str = "CERT-2025-A",
    lat: str = "9.314206",
    lng: str = "9.468153",
    captured_at: int | None = None,
    tamper_hash: str | None = None,
) -> dict:
    if captured_at is None:
        captured_at = int(time.time() * 1000)

    components = [
        officer_id, cert_event, farmer_id, plot_id,
        lot_seal, str(quantity_kg), lat, lng, str(captured_at),
    ]
    audit_hash = hashlib.sha256("|".join(components).encode()).hexdigest()
    client_node_id = f"NODE-{captured_at % 10_000_000:07X}"

    return {
        "nodeId": client_node_id,
        "schemaVersion": "1.0",
        "syncStatus": "pending",
        "timestamp": captured_at,
        "auditHash": tamper_hash or audit_hash,
        "event": {"officerId": officer_id, "certEvent": cert_event},
        "farmer": {"farmerId": farmer_id, "plotId": plot_id},
        "seed": {"variety": "NICOLA-A", "lotSeal": lot_seal, "quantityKg": quantity_kg},
        "gps": {"lat": lat, "lng": lng, "accuracy": 12.0, "capturedAt": captured_at},
        "deviceInfo": {"userAgent": "Mozilla/5.0 (test)", "online": False},
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestAuditHashVerification:

    @pytest.mark.asyncio
    async def test_valid_hash_accepted(self, client, seeded_authority):
        payload = _build_field_payload(farmer_id="FM-0041")
        response = await client.post("/api/v1/nodes", json=payload)

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["hash_verified"] is True
        assert body["farmer_id"] == "FM-0041"
        assert body["lga_code"] == "PLT"
        assert body["node_id"].startswith("NGA-PLT-")

    @pytest.mark.asyncio
    async def test_tampered_hash_rejected(self, client, seeded_authority):
        payload = _build_field_payload(
            farmer_id="FM-0042",
            tamper_hash="0" * 64,
        )
        response = await client.post("/api/v1/nodes", json=payload)

        assert response.status_code == 422
        assert response.json()["detail"]["error"] == "audit_hash_mismatch"

    @pytest.mark.asyncio
    async def test_hash_mismatch_after_field_modification(self, client, seeded_authority):
        """Quantity inflated after hash was computed — server must reject."""
        payload = _build_field_payload(farmer_id="FM-0043", quantity_kg=50)
        payload["seed"]["quantityKg"] = 500
        response = await client.post("/api/v1/nodes", json=payload)

        assert response.status_code == 422
        assert response.json()["detail"]["error"] == "audit_hash_mismatch"


class TestIdempotency:

    @pytest.mark.asyncio
    async def test_duplicate_submission_returns_existing_node(self, client, seeded_authority):
        captured_at = int(time.time() * 1000) - 5000
        payload = _build_field_payload(farmer_id="FM-0044", captured_at=captured_at)

        r1 = await client.post("/api/v1/nodes", json=payload)
        r2 = await client.post("/api/v1/nodes", json=payload)

        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["node_id"] == r2.json()["node_id"], (
            "Duplicate submission should return the same node, not create a second."
        )


class TestFieldToReconciliation:

    @pytest.mark.asyncio
    async def test_field_node_appears_in_reconciliation(self, client, seeded_authority):
        """Full chain: field registration → seasonal report → reconciliation."""

        # Step 1 — register node via field form
        captured_at = int(time.time() * 1000) - 10_000
        payload = _build_field_payload(
            farmer_id="FM-0045",
            plot_id="PLT-B",  # 1.2 ha
            captured_at=captured_at,
        )
        reg_response = await client.post("/api/v1/nodes", json=payload)
        assert reg_response.status_code == 201, reg_response.text
        node_id = reg_response.json()["node_id"]

        # Step 2 — submit seasonal report with actual delivery
        report_response = await client.post(
            f"/nodes/{node_id}/report",
            json={
                "season": "2025-wet",
                "promised_delivery_kg": 14_400,
                "actual_delivery_kg": 13_920,
            },
        )
        assert report_response.status_code == 201, report_response.text

        # Step 3 — run reconciliation
        recon_response = await client.post(
            "/reconciliation/run",
            json={
                "manufacturer_id": "TEST-MANUFACTURER",
                "crop": "irish_potato",
                "quantity_kg": 10_000,
                "target_season": "2025-wet",
            },
        )
        assert recon_response.status_code in (200, 201), recon_response.text
        recon = recon_response.json()

        # Step 4 — verify field-registered node contributed supply
        assert recon["coverage_status"] in ("covered", "surplus"), (
            f"Expected coverage. Got {recon['coverage_status']}. "
            f"Verified supply: {recon['verified_supply_kg']} kg."
        )
        assert recon["verified_supply_kg"] > 0
        assert recon["nodes_eligible"] >= 1

    @pytest.mark.asyncio
    async def test_unverified_node_rejected_at_report_submission(self, client):
        """A node_id that does not exist cannot submit a report."""
        response = await client.post(
            "/nodes/NGA-PLT-2024-9999/report",
            json={"season": "2025-wet", "promised_delivery_kg": 20_000},
        )
        assert response.status_code in (403, 404)

    @pytest.mark.asyncio
    async def test_shortfall_scenario(self, client, seeded_authority):
        """Demand far exceeding verified supply returns shortfall with enrollment recommendation."""
        recon_response = await client.post(
            "/reconciliation/run",
            json={
                "manufacturer_id": "CWAY-FOODS",
                "crop": "irish_potato",
                "quantity_kg": 2_000_000,
                "target_season": "2025-wet",
            },
        )
        assert recon_response.status_code in (200, 201), recon_response.text
        recon = recon_response.json()

        assert recon["coverage_status"] == "shortfall"
        assert recon["gap_kg"] > 0
        assert recon["recommended_enrollments"] > 0
        assert isinstance(recon["top_nodes_by_lga"], dict)


class TestAuditChainIntegrity:

    @pytest.mark.asyncio
    async def test_audit_chain_intact_after_registrations(self, client, db_setup):
        """Audit chain endpoint reports chain_intact: true.

        Requires db_setup (not seeded_authority) so it runs even if no
        registrations have occurred — an empty chain is also valid.
        """
        response = await client.get("/audit/chain-check")
        assert response.status_code == 200
        body = response.json()
        assert body["chain_intact"] is True, (
            f"Audit chain broken: {body.get('message')}"
        )
