"""Keep deployment inventory synchronized and source approval evidence-based."""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from backend.app.core.config import Settings
from scripts.ingest_official_source import Text, ingest


def test_environment_inventory_covers_actual_settings_and_frontend_reads():
    root = Path(__file__).resolve().parents[2]
    inventory = (root / "docs/environment.md").read_text(encoding="utf-8")
    names = set(Settings.model_fields)
    for source in (root / "frontend/src").rglob("*.ts*"):
        names.update(
            re.findall(r"import\.meta\.env\.(VITE_[A-Z_]+)", source.read_text(encoding="utf-8"))
        )
    assert all(f"`{name}`" in inventory for name in names)
    backend_example = (root / "backend/.env.example").read_text(encoding="utf-8")
    assert all(
        re.search(rf"(?m)^(?:# )?{name}=", backend_example) for name in Settings.model_fields
    )


def test_hidden_script_and_style_cannot_supply_an_approved_passage():
    parser = Text()
    parser.feed(
        "<p>Visible public text</p><script>Invented routing authority</script><style>Other fabricated passage</style>"
    )
    visible = " ".join(parser.parts)
    assert "Visible public text" in visible
    assert "Invented" not in visible and "fabricated" not in visible


@pytest.mark.asyncio
async def test_source_ingestion_refuses_a_passage_absent_from_the_fetched_document(
    tmp_path, monkeypatch
):
    from scripts import ingest_official_source

    file = tmp_path / "approved.txt"
    file.write_text("A passage missing from the fetched page", encoding="utf-8")

    async def fetch(url):
        return "<p>A different document</p>"

    monkeypatch.setattr(ingest_official_source.SafeFetcher, "fetch_page", fetch)
    args = SimpleNamespace(
        authority="Isolated test authority",
        jurisdiction="Isolated jurisdiction",
        title="Isolated test document",
        url="https://official.example.invalid/rules",
        passage_file=file,
        verified_official=True,
    )
    with pytest.raises(ValueError, match="exact approved passage"):
        await ingest(args)
