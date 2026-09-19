from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.runs.router import router as runs_router

app = FastAPI(title="hackspain")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(runs_router, prefix="/api/runs", tags=["runs"])


@app.get("/health")
def health():
    return {"status": "ok"}
