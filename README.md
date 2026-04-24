# MovelAgro — Verified Supply Protocol

A backend protocol where every data point is anchored to a physical
certification event. Manufacturers receive demand gap analyses they can trust.
Insurers and banks can eventually extend credit against verified supply.

---

## The Architectural Argument

Most agricultural data platforms fail for the same reason: they accept
farmer-reported data with no mechanism to verify who is reporting or whether
the farm exists. The result is self-reported numbers that systematically
overstate supply — exactly the wrong signal for a manufacturer deciding how
much to procure or a bank deciding whether to extend crop financing.

MovelAgro solves this at the identity layer. A node (a farm) can only be
created in the system by a recognised **Certification Authority** — in this
deployment, the National Root Crops Research Institute (NRCRI) — during a
physical certification event: certified seed distribution. The field officer
who hands over the seed bag simultaneously registers the farm. The GPS
coordinates, seed lot ID, and event ID are locked into an immutable record at
that moment. The farmer does not self-register. There is no API key to share,
no form to submit from a phone the farmer may not own.

Once a node exists, every seasonal report it submits is trusted *because the
identity was established first*. An unverified node — one that was created
without a valid certification event — cannot submit data. The API returns HTTP
403 with an explicit rejection message. This is not a validation error; it is
an architectural boundary. The protocol refuses to accept data whose provenance
cannot be traced to a physical event.

The third layer is reconciliation. When a manufacturer signals demand —
"I need 400,000 kg of irish potato for the 2025 wet season" — the system
queries the verified node pool, excludes nodes whose historical delivery
reliability falls below a configurable threshold (default: 85%), and returns a
structured gap analysis: how much verified supply exists, how large the
shortfall is, and which LGAs have the most reliable nodes to enrol. The result
is a number a procurement officer can act on, not an estimate from a survey.

---

## Quickstart

```bash
# Start the full stack (Postgres + API + seed data)
docker-compose up

# Wait until you see: "Seed complete."
# Then hit the reconciliation endpoint:

# Shortfall scenario — demand exceeds verified supply
curl -s -X POST http://localhost:8000/reconciliation/run \
  -H "Content-Type: application/json" \
  -d '{
    "manufacturer_id": "CWAY-FOODS",
    "crop": "irish_potato",
    "quantity_kg": 2000000,
    "target_season": "2025-wet"
  }' | python3 -m json.tool

# Covered scenario — demand within verified supply
curl -s -X POST http://localhost:8000/reconciliation/run \
  -H "Content-Type: application/json" \
  -d '{
    "manufacturer_id": "CWAY-FOODS",
    "crop": "irish_potato",
    "quantity_kg": 150000,
    "target_season": "2025-wet"
  }' | python3 -m json.tool
```

### Register a new node (field officer workflow)

```bash
curl -s -X POST http://localhost:8000/nodes/register \
  -H "Content-Type: application/json" \
  -d '{
    "farmer_name": "Miriam Dung",
    "phone": "+234-803-111-2222",
    "certification_authority_id": 1,
    "certification_event_id": "NRCRI-SEED-DIST-2025-PLT-001",
    "seed_lot_id": "SL-2025-CIP-0001",
    "lga_code": "PLT",
    "gps_lat": 9.899,
    "gps_lon": 8.880,
    "hectares": 2.5
  }' | python3 -m json.tool
```

### Attempt to submit from an unverified node (the rejection demo)

```bash
curl -s -X POST http://localhost:8000/nodes/NGA-PLT-2024-9999/report \
  -H "Content-Type: application/json" \
  -d '{
    "season": "2024-wet",
    "promised_delivery_kg": 20000
  }' | python3 -m json.tool
```

Expected response:
```json
{
  "detail": "Node NGA-PLT-2024-9999 has no verified certification event. Data cannot be accepted into the protocol before identity is established."
}
```

### Audit chain integrity check

```bash
curl -s http://localhost:8000/audit/chain-check | python3 -m json.tool
# {"chain_intact": true, "message": "OK"}
```

---

## What the Reconciliation Output Means

A `POST /reconciliation/run` response looks like this:

```json
{
  "id": 1,
  "demand_signal_id": 1,
  "demand_kg": 2000000,
  "verified_supply_kg": 276480.0,
  "gap_kg": 1723520.0,
  "coverage_status": "shortfall",
  "hectares_needed": 144,
  "nodes_eligible": 18,
  "nodes_excluded_reliability": 2,
  "recommended_enrollments": 9,
  "top_nodes_by_lga": {
    "PLT": ["NGA-PLT-2023-0001", "NGA-PLT-2023-0002", ...],
    "JOS": ["NGA-JOS-2023-0001", ...],
    "BKS": ["NGA-BKS-2023-0001", ...]
  }
}
```

**Who reads it:** The manufacturer's procurement team and the NRCRI field
coordinator.

**What they do with it:**
- `coverage_status: "shortfall"` means the manufacturer cannot be supplied from
  the current verified network. The `recommended_enrollments` field tells the
  field coordinator how many additional farms to certify before the season opens.
- `nodes_excluded_reliability: 2` means 2 farms were dropped from the pool
  because their historical delivery rate was below the 85% threshold — visible
  accountability for underperformance.
- `top_nodes_by_lga` is the enrollment priority list: certify farms in the
  LGAs where the most reliable nodes already exist.

---

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

---

## API Documentation

With the stack running, visit:
- **http://localhost:8000/docs** — Swagger UI (full interactive docs)
- **http://localhost:8000/redoc** — ReDoc

---

## Year 2 Scope

The protocol is intentionally narrow. What comes next, once the verification
layer is proven:

- **Insurer access** — crop insurance products priced against verified yield
  history per node, not blanket actuarial tables
- **Bank credit scoring** — seasonal credit limits derived from a node's
  delivery reliability score
- **Extension officer interface** — agronomic advisory keyed to the certified
  seed lot and season, so recommendations are traceable to what was actually
  planted
- **Multi-authority support** — other state research institutes onboarded as
  certification authorities, scoped to their own geographies
- **Mobile-first report submission** — lightweight USSD or SMS interface for
  farmers in areas with intermittent data connectivity

None of this requires changing the core invariant: the trust anchor remains the
physical certification event. Everything downstream derives its reliability from
that moment.

---

## Project Structure

```
movelagro/
├── main.py                      FastAPI entrypoint
├── config.py                    All configurable constants
├── database.py                  Async SQLAlchemy engine + session
├── models/
│   ├── authority.py             CertificationAuthority
│   ├── node.py                  Node (trust anchor record)
│   ├── report.py                SeasonalReport
│   ├── demand.py                DemandSignal
│   ├── reconciliation.py        ReconciliationResult
│   └── audit.py                 AuditEntry (hash chain)
├── api/
│   ├── registration.py          POST /nodes/register
│   ├── reporting.py             POST /nodes/{id}/report, GET /nodes/{id}/history
│   └── reconciliation.py        POST /reconciliation/run, GET /reconciliation/{id}
├── core/
│   ├── id_generator.py          Deterministic NGA-LGA-YEAR-NNNN IDs
│   ├── audit_chain.py           SHA-256 hash chain writes
│   └── reconciliation_engine.py Pure supply/demand logic
├── seed_data/generate.py        20 nodes × 3 seasons demo data
├── tests/test_reconciliation.py 4 architectural tests
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```
