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
    print("\nSeed complete. Try: POST /reconciliation/run")

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
