"""Generate initial DDL only before first deployment. Never rewrite applied migrations."""

import sys
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.database.models.foundation import Base

root = Path(__file__).resolve().parents[1]
tables = [t for t in Base.metadata.sorted_tables if t.schema != "auth"]
dialect = postgresql.dialect()
parts = [
    "-- Initial foundation: review against the target Supabase database before applying.\nBEGIN;",
    "CREATE EXTENSION IF NOT EXISTS postgis;",
    "CREATE EXTENSION IF NOT EXISTS vector;",
    "CREATE EXTENSION IF NOT EXISTS pgcrypto;",
]
for table in tables:
    parts.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ";")
    for index in sorted(table.indexes, key=lambda i: i.name):
        parts.append(str(CreateIndex(index).compile(dialect=dialect)).strip() + ";")
parts.append((root / "supabase/policies.sql").read_text(encoding="utf-8"))
parts.append("COMMIT;\n")
output = "\n".join(line.rstrip() for line in "\n\n".join(parts).splitlines()) + "\n"
target = root / "supabase/migrations/0001_foundation.sql"
if "--check" in sys.argv:
    if target.read_text(encoding="utf-8") != output:
        raise SystemExit("Initial migration differs from model/policy sources")
else:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(output, encoding="utf-8")
