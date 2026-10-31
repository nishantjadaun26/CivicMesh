from unittest.mock import AsyncMock

import pytest
from civicmesh_ai import cli


def test_cli_requires_explicit_paid_call_flag(monkeypatch):
    call = AsyncMock()
    monkeypatch.setattr(cli, "extract_file", call)
    monkeypatch.setattr("sys.argv", ["civicmesh-extract", "--text-file", "unused.txt"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    call.assert_not_called()
