from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.graph.router import router as graph_router
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
app.include_router(graph_router, prefix="/api/graph", tags=["graph"])


@app.get("/health")
def health():
    return {"status": "ok"}
