"""Startup validation must not print credential inputs in Pydantic tracebacks."""

import pytest
from backend.app.core.config import Settings
from pydantic import ValidationError


def test_settings_validation_and_repr_redact_secret_fields():
    private_marker = "isolated-secret-value-never-a-real-credential"
    with pytest.raises(ValidationError) as failure:
        Settings(
            _env_file=None,
            DATABASE_URL="invalid-url-with-" + private_marker,
            SUPABASE_SERVICE_ROLE_KEY=private_marker,
            GEMINI_API_KEY=private_marker,
        )
    assert private_marker not in str(failure.value)
    settings = Settings(
        _env_file=None,
        GEMINI_API_KEY=private_marker,
        SUPABASE_SERVICE_ROLE_KEY=private_marker,
        CHECKPOINT_DATABASE_URL=private_marker,
    )
    assert private_marker not in repr(settings)


def test_production_database_tls_requires_certificate_and_hostname_verification():
    import ssl

    from backend.app.core.tls import checkpoint_tls, database_tls

    settings = Settings(_env_file=None).model_copy(update={"ENVIRONMENT": "production"})
    context = database_tls(settings)
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    assert checkpoint_tls(settings) == {"sslmode": "verify-full", "sslrootcert": "system"}
    custom = settings.model_copy(update={"DATABASE_SSL_ROOT_CERT": "/operator-provided/ca.crt"})
    assert checkpoint_tls(custom)["sslrootcert"] == "/operator-provided/ca.crt"
