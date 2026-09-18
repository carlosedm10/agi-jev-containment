from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.items.router import router as items_router

app = FastAPI(title="hackspain")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(items_router, prefix="/api/items", tags=["items"])


@app.get("/health")
def health():
    return {"status": "ok"}
