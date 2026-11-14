"""RARecruit FastAPI entrypoint: creates the app and registers routers.

Keep this file small: app setup, middleware and ``include_router`` calls only.
Endpoints go in ``app/routers/<feature>.py``; auth helpers live in ``app/auth.py``.

Adding a feature router:
    1. Create ``app/routers/<feature>.py`` with ``router = APIRouter(...)``.
       For interviewer/board-only features, protect the whole router:
           APIRouter(prefix="/grading",
                     dependencies=[Depends(require_role(INTERVIEWER, BOARD))])
    2. Import it below and add ``app.include_router(<feature>.router)``.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import me

app = FastAPI(title="RARecruit API")

# CORS: browsers block JavaScript on one origin (the Next.js app,
# e.g. http://localhost:3000) from calling another (this API on :8000)
# unless the API explicitly allows it. Only our frontend's origin is allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    # We authenticate with an "Authorization: Bearer" header, not cookies,
    # so browsers don't need to send credentials (cookies) cross-origin.
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    # Authorization carries the Supabase token; Content-Type is for JSON bodies.
    allow_headers=["Authorization", "Content-Type"],
)

# --- Routers -----------------------------------------------------------------
app.include_router(me.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Public: no sign-in required.

    Returns:
        {"status": "ok"} when the server is running.
    """
    return {"status": "ok"}
