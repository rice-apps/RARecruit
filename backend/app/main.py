"""RARecruit FastAPI entrypoint: creates the app and registers routers."""

from fastapi import FastAPI

app = FastAPI(title="RARecruit API")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check.

    Returns:
        {"status": "ok"} when the server is running.
    """
    return {"status": "ok"}
