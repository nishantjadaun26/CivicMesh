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
