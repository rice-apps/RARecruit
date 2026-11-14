"""App settings loaded from environment variables (and ``backend/.env``).

Import the shared instance anywhere you need a setting:

    from app.config import settings
    settings.supabase_url

Every variable here must also be listed in ``backend/.env.example``.
"""

from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env, found relative to this file so it loads no matter which
# directory uvicorn/pytest is started from.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Typed app configuration.

    Field names map to env vars case-insensitively, e.g. ``supabase_url`` is
    read from ``SUPABASE_URL``. Real environment variables take priority over
    values in ``.env``.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        # Ignore unrelated variables instead of failing on them.
        extra="ignore",
    )

    # --- Supabase (required) -------------------------------------------------
    # Project URL, e.g. "https://<project-ref>.supabase.co".
    supabase_url: str
    # Server-only key that bypasses Row Level Security. SecretStr hides it in
    # logs/reprs; call .get_secret_value() only where the client is created.
    supabase_service_role_key: SecretStr

    # --- CORS ----------------------------------------------------------------
    # Origin of the Next.js app allowed to call this API.
    frontend_origin: str = "http://localhost:3000"

    # --- Google service account (Forms + Calendar) ---------------------------
    # For the account that owns the Google Form and sends Calendar invites,
    # NOT for user sign-in (that's Supabase Auth). Optional so the API can
    # start before the Intake/Scheduling features are set up.
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    google_refresh_token: SecretStr = SecretStr("")
    google_form_id: str = ""

    @field_validator("supabase_url", "frontend_origin")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        """Normalize URLs so code can safely append paths.

        Args:
            value: The raw URL from the environment.

        Returns:
            The URL without a trailing slash (and without surrounding spaces).
        """
        return value.strip().rstrip("/")

    @field_validator("supabase_url")
    @classmethod
    def _require_http_url(cls, value: str) -> str:
        """Reject an empty or non-URL ``SUPABASE_URL`` with a clear message.

        Args:
            value: The (already normalized) Supabase project URL.

        Returns:
            The same URL if it looks valid.

        Raises:
            ValueError: If the URL doesn't start with http(s)://.
        """
        # http:// is allowed for a local Supabase stack (`supabase start`).
        if not value.startswith(("https://", "http://")):
            raise ValueError(
                "SUPABASE_URL must be the project URL, e.g. https://<ref>.supabase.co"
            )
        return value


# Created once at import. Missing required variables raise a ValidationError
# here at startup, naming the variable, instead of failing on first request.
settings = Settings()
