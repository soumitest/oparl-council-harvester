CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS iris_staging;

CREATE TABLE IF NOT EXISTS iris_staging.signal_ingest (
    id               BIGSERIAL PRIMARY KEY,
    source_system    TEXT        NOT NULL,   -- OParl System URL
    source_id        TEXT        NOT NULL,   -- OParl object id (a URL)
    object_type      TEXT        NOT NULL,   -- Paper
    title            TEXT,
    source_url       TEXT,                   -- human-readable web link
    published_at     TIMESTAMPTZ,            -- Paper.date (fallback: Paper.created)
    matched_keywords TEXT[]      NOT NULL DEFAULT '{}',
    body_name        TEXT,                   -- municipality (OParl Body.name)
    body_ags         TEXT,                   -- official municipality key (may be NULL)
    location_text    TEXT,
    geom             geometry(Point, 25832),
    geom_status      TEXT        NOT NULL DEFAULT 'none'
        CHECK (geom_status IN ('resolved', 'unresolved', 'invalid', 'none')),
    geom_note        TEXT,                   -- why a location is unresolved / invalid
    raw              JSONB       NOT NULL,
    ingested_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT signal_ingest_source_uq UNIQUE (source_system, source_id),
    CONSTRAINT signal_ingest_geom_consistent
        CHECK ((geom_status = 'resolved') = (geom IS NOT NULL))
);

-- Safe to re-run on a table created by an earlier version of this file.
ALTER TABLE iris_staging.signal_ingest ADD COLUMN IF NOT EXISTS body_name TEXT;
ALTER TABLE iris_staging.signal_ingest ADD COLUMN IF NOT EXISTS body_ags  TEXT;
ALTER TABLE iris_staging.signal_ingest ADD COLUMN IF NOT EXISTS geom_note TEXT;

CREATE INDEX IF NOT EXISTS signal_ingest_geom_gix
    ON iris_staging.signal_ingest USING GIST (geom);
CREATE INDEX IF NOT EXISTS signal_ingest_published_ix
    ON iris_staging.signal_ingest (published_at);
