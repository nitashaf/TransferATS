from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.api import resume, job, match, candidates


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="TransferATS",
    description=(
        "AI-powered resume screening API with three-layer matching: "
        "ATS keyword scoring, semantic similarity (Gemini embeddings), "
        "and transferable skills detection."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume.router, prefix="/api/resume", tags=["Resume"])
app.include_router(job.router, prefix="/api/job", tags=["Job"])
app.include_router(match.router, prefix="/api/match", tags=["Match"])
app.include_router(candidates.router, prefix="/api/candidates", tags=["Candidates"])


@app.get("/", tags=["Health"])
async def root():
    return {"service": "TransferATS", "version": "1.0.0", "docs": "/docs"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}
