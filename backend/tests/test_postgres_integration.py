"""Disposable PostgreSQL migrations/RLS/checkpoint/lock tests, never a production DSN."""

import os
from pathlib import Path
from uuid import uuid4

import pytest

DSN = os.environ.get("CIVICMESH_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not DSN, reason="Disposable PostgreSQL test URL is not configured")


@pytest.mark.asyncio
async def test_migrations_rls_storage_postgis_checkpoints_and_session_locks():
    import psycopg
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.conninfo import conninfo_to_dict
    from psycopg.rows import dict_row
    config = conninfo_to_dict(DSN)
    assert config.get("host") in {"127.0.0.1", "localhost"}, "Test database must be loopback-only"
    assert config.get("dbname") == "civicmesh_test", "Refuse to modify any other database"
    root = Path(__file__).resolve().parents[2]
    async with await psycopg.AsyncConnection.connect(DSN, autocommit=True, row_factory=dict_row) as connection:
        # Minimal Auth and Storage schemas are test doubles for the managed services.
        # PostgreSQL, PostGIS, vector, migration SQL, RLS and advisory locks are real.
        await connection.execute("""
          DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon; END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated; END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN CREATE ROLE service_role; END IF;
          END $$;
          CREATE SCHEMA IF NOT EXISTS auth;
          CREATE SCHEMA IF NOT EXISTS storage;
          CREATE TABLE IF NOT EXISTS auth.users(id uuid PRIMARY KEY);
          CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS
            $$ SELECT nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
          CREATE TABLE IF NOT EXISTS storage.buckets(id text PRIMARY KEY,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
          CREATE TABLE IF NOT EXISTS storage.objects(id uuid PRIMARY KEY,bucket_id text,name text);
          ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;
          GRANT USAGE ON SCHEMA public, auth, storage TO anon, authenticated;
        """)
        for migration in sorted((root / "supabase/migrations").glob("*.sql")):
            await connection.execute(migration.read_text(encoding="utf-8"))
        await connection.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public, storage TO anon, authenticated")
        owner, other, report, evidence = uuid4(), uuid4(), uuid4(), uuid4()
        await connection.execute("INSERT INTO auth.users(id) VALUES (%s),(%s)", (owner, other))
        await connection.execute("INSERT INTO public.profiles(id) VALUES (%s),(%s)", (owner, other))
        await connection.execute("INSERT INTO public.reports(id,owner_id,text,latitude,longitude,location_confirmed) VALUES(%s,%s,'isolated observation',1,2,true)", (report, owner))
        point = (await (await connection.execute("SELECT ST_X(location) AS x,ST_Y(location) AS y FROM public.reports WHERE id=%s", (report,))).fetchone())
        assert point == {"x": 2.0, "y": 1.0}
        await connection.execute("INSERT INTO public.evidence(id,owner_id,report_id,storage_bucket,storage_path,mime_type,file_size_bytes,verified) VALUES(%s,%s,%s,'civicmesh-evidence','isolated-photo','image/jpeg',3,true)", (evidence, owner, report))
        await connection.execute("INSERT INTO storage.objects(id,bucket_id,name) VALUES(%s,'civicmesh-evidence','isolated-photo')", (uuid4(),))
        await connection.execute("SET ROLE authenticated")
        await connection.execute("SELECT set_config('request.jwt.claim.sub',%s,false)", (str(other),))
        assert await (await connection.execute("SELECT id FROM public.reports")).fetchall() == []
        assert await (await connection.execute("SELECT id FROM storage.objects")).fetchall() == []
        await connection.execute("SELECT set_config('request.jwt.claim.sub',%s,false)", (str(owner),))
        assert len(await (await connection.execute("SELECT id FROM public.reports")).fetchall()) == 1
        assert len(await (await connection.execute("SELECT id FROM storage.objects")).fetchall()) == 1
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await connection.execute("UPDATE public.reports SET status='processed'")
        await connection.execute("RESET ROLE")
        await connection.execute("SET search_path=civicmesh_checkpoints,public")
        saver = AsyncPostgresSaver(connection)
        await saver.setup()
        assert await saver.aget_tuple({"configurable": {"thread_id": "isolated-empty"}}) is None
        await connection.execute("SET ROLE authenticated")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await connection.execute("SELECT * FROM civicmesh_checkpoints.checkpoints")
        await connection.execute("RESET ROLE")
        lock_key = 682091
        assert (await (await connection.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (lock_key,))).fetchone())["acquired"]
        async with await psycopg.AsyncConnection.connect(DSN, autocommit=True) as second:
            assert not (await (await second.execute("SELECT pg_try_advisory_lock(%s)", (lock_key,))).fetchone())[0]
        await connection.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))
