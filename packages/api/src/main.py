from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routes import cases, upload, intake, review, agents

app = FastAPI(
    title="DEFENDER AI API",
    description="Public Defender AI Assistant — Agent Backend",
    version="0.1.0",
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
