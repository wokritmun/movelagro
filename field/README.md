# MovelAgro Field Registration

Offline-first PWA for field officers. Runs on any Android device with a browser. No app store. No connectivity required at point of registration.

## What it does

A field officer opens `register.html` on their Android device. The four-step form captures:

1. **Officer ID** — selected from pre-loaded list, no free-text
2. **Farmer identity** — selected from pre-enrolled cohort, plot locked at this step
3. **Seed lot & quantity** — variety, certified lot seal number, kg distributed
4. **GPS coordinate** — device location captured at moment of physical handoff

On submit, the record is saved to **IndexedDB** with `syncStatus: "pending"` and a **SHA-256 audit hash** generated from all field values + GPS + timestamp. The hash is stored with the record and included in the POST to `/api/v1/nodes` — the backend verifies it on receipt.

When connectivity returns, pending records sync automatically. The service worker (`sw.js`) also handles background sync via the [Background Sync API](https://developer.mozilla.org/en-US/docs/Web/API/Background_Synchronization_API) on supported browsers.

## Why offline-first

Pankshin LGA has intermittent mobile data. Registration events occur at seed distribution points — outdoors, often with poor signal. The architecture assumes no connectivity during the registration workflow and treats sync as an eventual background process, not a blocking requirement.

## Files

```
field/
  register.html   — complete PWA shell (single file, no build step)
  sw.js           — service worker for shell caching + background sync
  README.md       — this file
```

## Running locally

```bash
# Any static server works — file:// origin blocks service worker registration
# but IndexedDB storage and GPS still function
python3 -m http.server 8000
# open http://localhost:8000/field/register.html
```

## Node record schema

```json
{
  "nodeId": "NODE-LZ4K3RJ",
  "schemaVersion": "1.0",
  "syncStatus": "pending",
  "timestamp": 1714089600000,
  "auditHash": "3a9f2c...",
  "event": {
    "officerId": "FO-PNK-001",
    "certEvent": "CERT-2025-A"
  },
  "farmer": {
    "farmerId": "FM-0041",
    "plotId": "PLT-A"
  },
  "seed": {
    "variety": "NICOLA-A",
    "lotSeal": "LOT-NIC-2025-0088",
    "quantityKg": 50
  },
  "gps": {
    "lat": "9.314206",
    "lng": "9.468153",
    "accuracy": 12,
    "capturedAt": 1714089612341
  },
  "deviceInfo": {
    "userAgent": "...",
    "online": false
  }
}
```

The `auditHash` field is the SHA-256 of all identity-bearing fields concatenated with `|` separators. The backend recomputes the hash on receipt and rejects records where it does not match — this is the tamper-detection layer referenced in the reconciliation engine.
