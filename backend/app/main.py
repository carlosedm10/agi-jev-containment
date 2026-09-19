from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.graph.neo4j import neo4j_graph
from app.graph.router import router as graph_router
from app.realtime.router import router as realtime_router
from app.runs.router import router as runs_router
from app.world.router import router as world_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    await neo4j_graph.setup()
    yield
    await neo4j_graph.close()


app = FastAPI(title="hackspain", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(runs_router, prefix="/api/runs", tags=["runs"])
app.include_router(realtime_router, prefix="/api/runs", tags=["realtime"])
app.include_router(graph_router, prefix="/api/graph", tags=["graph"])
app.include_router(world_router, prefix="/api/world", tags=["world"])


@app.get("/health")
def health():
    return {"status": "ok"}
