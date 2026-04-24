CROP = "irish_potato"
CERTIFICATION_AUTHORITY_NAME = "NRCRI"
GEOGRAPHY = "Jos Plateau, Nigeria"
SEASON_STRUCTURE = ["wet", "dry"]
DELIVERY_RELIABILITY_THRESHOLD = 0.85
NODE_ID_FORMAT = "{iso_country}-{lga_code}-{year}-{sequence:04d}"
ISO_COUNTRY = "NGA"
DEFAULT_AVG_YIELD_KG_PER_HA = 12_000.0

import os
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://movelagro:movelagro@localhost/movelagro"
)
