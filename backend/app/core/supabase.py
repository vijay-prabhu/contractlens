from supabase import create_client, Client
from functools import lru_cache

from app.core.config import get_settings

settings = get_settings()


@lru_cache
def get_supabase_client() -> Client:
    """Get cached Supabase client instance."""
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,  # Using service role for server-side operations
    )


def get_storage_client():
    """Get Supabase storage client."""
    client = get_supabase_client()
    return client.storage
