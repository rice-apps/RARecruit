"""Shared Supabase client for database access.

Import it wherever you need the database:

    from app.db import supabase
    supabase.table("interviewers").select("*").execute()

SECURITY: this client uses the service-role key, which BYPASSES Row Level
Security. Every query runs with full access, so routers must check
permissions themselves (see ``app.auth``) before reading or writing data.
Never send this key, or this client's raw results, to the frontend unfiltered.
"""

from supabase import Client, create_client

from app.config import settings

# One client for the whole app: creating it is cheap, but reusing it shares the
# underlying HTTP connection pool. It's synchronous, so call it from `def`
# (not `async def`) routes/dependencies; FastAPI runs those in a thread pool.
supabase: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key.get_secret_value(),
)
