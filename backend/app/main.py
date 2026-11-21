"""RARecruit FastAPI entrypoint: creates the app and registers routers."""

from fastapi import FastAPI
from app.routers.scheduling.intake import router as intake_router

app = FastAPI(title="RARecruit API")
app.include_router(intake_router)

@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check.

    Returns:
        {"status": "ok"} when the server is running.
    """
    return {"status": "ok"}
