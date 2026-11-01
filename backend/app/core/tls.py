"""Verified database TLS with optional owner-provided Supabase CA certificate."""

import ssl


def database_tls(settings):
    context = ssl.create_default_context()
    if settings.DATABASE_SSL_ROOT_CERT:
        context.load_verify_locations(cafile=settings.DATABASE_SSL_ROOT_CERT)
    return context


def checkpoint_tls(settings):
    if settings.ENVIRONMENT != "production":
        return {}
    return {"sslmode": "verify-full", "sslrootcert": settings.DATABASE_SSL_ROOT_CERT or "system"}
