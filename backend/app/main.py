"""RARecruit FastAPI entrypoint: creates the app and registers routers."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.runs import router as runs_router

app = FastAPI(title="RARecruit API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:3001",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(runs_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check.

    Returns:
        {"status": "ok"} when the server is running.
    """
    return {"status": "ok"}
