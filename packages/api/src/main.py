from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routes import cases, upload, intake, review, agents
from src.services.model_gateway import check_configuration, current_mode, require_api_key


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Fail at startup, not on the first case: an allowlist/primary mismatch, or live
    # use without the user's own key, is an AuthError/config error now (§8.1).
    check_configuration()
    if current_mode() in ("live", "record"):
        require_api_key()
    yield


app = FastAPI(
    title="DEFENDER AI API",
    description="Public Defender AI Assistant — Agent Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(intake.router, prefix="/api/v1")
app.include_router(review.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
