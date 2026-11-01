"""Parse SQL migrations locally; execution and policy tests are separate checks."""

from pathlib import Path

from pglast import parse_sql


def main():
    directory = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
    for migration in sorted(directory.glob("*.sql")):
        statements = parse_sql(migration.read_text(encoding="utf-8"))
        print(f"Parsed {migration.name}: {len(statements)} statements")


if __name__ == "__main__":
    main()
