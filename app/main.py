"""Gateway: single entry point mounting every module under /api/v1."""
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.db import Base, SessionLocal, engine
from app.modules.audit.router import router as audit_router
from app.modules.cases.router import router as cases_router
from app.modules.matching.router import router as matching_router
from app.modules.matching.seed import seed_experts


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_experts(db)
    yield


app = FastAPI(title="Assistant d'investigation numerique", version="0.1.0", lifespan=lifespan)

api = APIRouter(prefix="/api/v1")


@api.get("/health", tags=["Gateway"])
def health():
    return {"status": "ok"}


for r in (audit_router, cases_router, matching_router):
    api.include_router(r)

app.include_router(api)
