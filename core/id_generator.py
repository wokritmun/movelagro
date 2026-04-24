from config import ISO_COUNTRY
from sqlalchemy import text

async def generate_node_id(session, lga_code: str, year: int) -> str:
    result = await session.execute(
        text("SELECT COUNT(*) FROM nodes WHERE lga_code = :lga AND node_id LIKE :prefix"),
        {"lga": lga_code, "prefix": f"{ISO_COUNTRY}-{lga_code}-{year}-%"},
    )
    count = result.scalar() or 0
    return f"{ISO_COUNTRY}-{lga_code}-{year}-{count + 1:04d}"
