import json
from unittest.mock import AsyncMock

import pytest
from civicmesh_ai import cli


def test_cli_requires_explicit_paid_call_flag(monkeypatch):
    """The command refuses paid work before reading files or constructing a provider."""
    call = AsyncMock()
    monkeypatch.setattr(cli, "extract_file", call)
    monkeypatch.setattr("sys.argv", ["civicmesh-extract", "--text-file", "unused.txt"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    call.assert_not_called()


def test_media_cli_arguments_require_explicit_consent(monkeypatch):
    """Media flags cannot bypass the paid-call and data-sharing gate."""
    call = AsyncMock()
    monkeypatch.setattr(cli, "extract_file", call)
    monkeypatch.setattr(
        "sys.argv",
        [
            "civicmesh-extract",
            "--media",
            "00000000-0000-0000-0000-000000000001",
            "audio/webm",
            "unused.webm",
        ],
    )
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    call.assert_not_called()


@pytest.mark.parametrize("configured", [False, True])
def test_config_check_is_offline_and_never_prints_credentials(monkeypatch, capsys, configured):
    """A local preflight checks presence only; it never implies billing verification."""
    call = AsyncMock()
    monkeypatch.setattr(cli, "extract_file", call)
    for name, value in [
        ("GEMINI_API_KEY", "private-test-key"),
        ("GEMINI_MODEL", "private-test-model"),
    ]:
        if configured:
            monkeypatch.setenv(name, value)
        else:
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("sys.argv", ["civicmesh-extract", "--check-config"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == (0 if configured else 1)
    output = capsys.readouterr().out
    assert "private-test-key" not in output and "private-test-model" not in output
    assert json.loads(output) == {
        "key_configured": configured,
        "model_configured": configured,
        "billing_status": "not_verified",
        "api_request_made": False,
    }
    call.assert_not_called()


@pytest.mark.parametrize("flag", ["--allow-api-call", "--allow-paid-call"])
def test_live_call_consent_uses_new_flag_and_preserves_compatibility(monkeypatch, flag):
    """Either explicit consent spelling permits only the requested extraction dispatch."""
    call = AsyncMock()
    monkeypatch.setattr(cli, "extract_file", call)
    monkeypatch.setattr("sys.argv", ["civicmesh-extract", "--text-file", "unused.txt", flag])
    cli.main()
    call.assert_awaited_once()
