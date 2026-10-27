"""PostgreSQL / PostGIS loading: idempotent upserts, one savepoint per record."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import psycopg
from psycopg.types.json import Jsonb

from .normalize import Record

log = logging.getLogger(__name__)

Outcome = Literal["inserted", "updated", "unchanged"]

SCHEMA_FILE = Path(__file__).resolve().parents[2] / "sql" / "001_schema.sql"

# ON CONFLICT ... WHERE: a row identical to the stored one is NOT touched
# (no RETURNING row -> "unchanged", updated_at stays as it was).
# xmax = 0 is true only for a freshly inserted row.
UPSERT_SQL = """
INSERT INTO iris_staging.signal_ingest AS t (
    source_system, source_id, object_type, title, source_url, published_at,
    matched_keywords, body_name, body_ags, location_text,
    geom, geom_status, geom_note, raw
) VALUES (
    %(source_system)s, %(source_id)s, %(object_type)s, %(title)s, %(source_url)s, %(published_at)s,
    %(matched_keywords)s, %(body_name)s, %(body_ags)s, %(location_text)s,
    CASE WHEN %(x)s::float8 IS NULL THEN NULL
         ELSE ST_SetSRID(ST_MakePoint(%(x)s::float8, %(y)s::float8), 25832) END,
    %(geom_status)s, %(geom_note)s, %(raw)s
)
ON CONFLICT (source_system, source_id) DO UPDATE SET
    title = EXCLUDED.title,
    source_url = EXCLUDED.source_url,
    published_at = EXCLUDED.published_at,
    matched_keywords = EXCLUDED.matched_keywords,
    body_name = EXCLUDED.body_name,
    body_ags = EXCLUDED.body_ags,
    location_text = EXCLUDED.location_text,
    geom = EXCLUDED.geom,
    geom_status = EXCLUDED.geom_status,
    geom_note = EXCLUDED.geom_note,
    raw = EXCLUDED.raw,
    updated_at = now()
WHERE (t.title, t.source_url, t.published_at, t.matched_keywords, t.body_name, t.body_ags,
       t.location_text, ST_AsEWKT(t.geom), t.geom_status, t.geom_note, t.raw)
      IS DISTINCT FROM
      (EXCLUDED.title, EXCLUDED.source_url, EXCLUDED.published_at, EXCLUDED.matched_keywords,
       EXCLUDED.body_name, EXCLUDED.body_ags, EXCLUDED.location_text, ST_AsEWKT(EXCLUDED.geom),
       EXCLUDED.geom_status, EXCLUDED.geom_note, EXCLUDED.raw)
RETURNING (xmax = 0) AS inserted
"""


def connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(database_url)


def init_schema(conn: psycopg.Connection, schema_file: Path = SCHEMA_FILE) -> None:
    """Apply sql/001_schema.sql (idempotent). Useful when not using docker-compose's init."""
    with conn.transaction():
        conn.execute(schema_file.read_text(encoding="utf-8"))


def upsert(conn: psycopg.Connection, rec: Record) -> Outcome:
    params = {
        "source_system": rec.source_system,
        "source_id": rec.source_id,
        "object_type": rec.object_type,
        "title": rec.title,
        "source_url": rec.source_url,
        "published_at": rec.published_at,
        "matched_keywords": rec.matched_keywords,
        "body_name": rec.body_name,
        "body_ags": rec.body_ags,
        "location_text": rec.location_text,
        "x": rec.x,
        "y": rec.y,
        "geom_status": rec.geom_status,
        "geom_note": rec.geom_note,
        "raw": Jsonb(rec.raw),
    }
    with conn.transaction():  # savepoint: one bad row does not abort the run
        row = conn.execute(UPSERT_SQL, params).fetchone()
    if row is None:
        return "unchanged"
    return "inserted" if row[0] else "updated"
