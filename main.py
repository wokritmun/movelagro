from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from database import engine, Base, get_session
from api import registration_router, reporting_router, reconciliation_router
from api.field_ingest import router as field_ingest_router
from core.audit_chain import verify_chain


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="MovelAgro Verified Supply Protocol",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(registration_router)
app.include_router(reporting_router)
app.include_router(reconciliation_router)
app.include_router(field_ingest_router)

# Serve the field registration PWA under /field/
app.mount("/field", StaticFiles(directory="field", html=True), name="field")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    return (
        '<html><body style="font-family:monospace;padding:2rem">'
        "<h2>MovelAgro</h2>"
        '<a href="/docs">API docs</a> | '
        '<a href="/audit/chain-check">Audit chain</a> | '
        '<a href="/field/register.html">Field registration</a>'
        "</body></html>"
    )


@app.get("/audit/chain-check", tags=["Audit"])
async def check_audit_chain(session: AsyncSession = Depends(get_session)):
    # Uses Depends(get_session) so the test SQLite override applies correctly.
    # The original used AsyncSessionLocal() directly, which bypassed the override.
    ok, message = await verify_chain(session)
    return {"chain_intact": ok, "message": message}
