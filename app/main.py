"""Gateway: single entry point mounting every module under /api/v1."""
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI

from app.db import Base, SessionLocal, ensure_columns, engine
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import current_user, router as auth_router
from app.modules.cases.router import router as cases_router
from app.modules.contracts.router import router as contracts_router
from app.modules.matching.router import router as matching_router
from app.modules.matching.seed import seed_experts
from app.modules.methodology.router import router as methodology_router
from app.modules.mission.router import router as mission_router
from app.modules.pv.nlp import get_nlp
from app.modules.pv.router import router as pv_router
from app.modules.reports.final import router as final_report_router
from app.modules.reports.tech import router as tech_report_router
from app.modules.workflow.router import router as workflow_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    ensure_columns(engine)
    with SessionLocal() as db:
        seed_experts(db)
    get_nlp()  # load spaCy once at startup so the first PV request is not slow
    yield


app = FastAPI(title="Locard", description="Assistant intelligent d'investigation numerique", version="0.1.0", lifespan=lifespan)

api = APIRouter(prefix="/api/v1")


@api.get("/health", tags=["Gateway"])
def health():
    return {"status": "ok"}


api.include_router(auth_router)  # public: register, login, refresh
# Every other router requires a valid access token, whatever its own endpoints declare.
for r in (audit_router, cases_router, matching_router, workflow_router, contracts_router, mission_router, pv_router,
          methodology_router, tech_report_router, final_report_router):
    api.include_router(r, dependencies=[Depends(current_user)])

app.include_router(api)
