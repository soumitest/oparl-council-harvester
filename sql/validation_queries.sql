-- Validation queries for iris_staging.signal_ingest
-- Run:  docker compose exec -T db psql -U iris -d iris -f - < sql/validation_queries.sql

-- 1. No duplicates (must return 0 rows)
SELECT source_system, source_id, count(*) FROM iris_staging.signal_ingest
GROUP BY 1, 2 HAVING count(*) > 1;

-- 2. Every geometry is a valid point in EPSG:25832 (must return 0)
SELECT count(*) AS bad_geometries FROM iris_staging.signal_ingest
WHERE geom IS NOT NULL AND (ST_SRID(geom) <> 25832 OR NOT ST_IsValid(geom) OR GeometryType(geom) <> 'POINT');

-- 3. Geometry status overview
SELECT geom_status, count(*) FROM iris_staging.signal_ingest GROUP BY 1 ORDER BY 2 DESC;

-- 4. Traceability: every row has a source id, a raw payload and a matched keyword (must return 0)
SELECT count(*) AS untraceable FROM iris_staging.signal_ingest
WHERE source_id IS NULL OR raw IS NULL OR cardinality(matched_keywords) = 0;

-- 5. Missing fields made visible
SELECT count(*) FILTER (WHERE title IS NULL)        AS no_title,
       count(*) FILTER (WHERE source_url IS NULL)   AS no_web_url,
       count(*) FILTER (WHERE published_at IS NULL) AS no_date
FROM iris_staging.signal_ingest;

-- 6. Rows by municipality and keyword
SELECT body_name, unnest(matched_keywords) AS keyword, count(*)
FROM iris_staging.signal_ingest GROUP BY 1, 2 ORDER BY 1, 3 DESC;

-- 7. Resolved points inside a 5 km buffer around Frankfurt Römerberg (EPSG:25832)
SELECT source_id, title FROM iris_staging.signal_ingest
WHERE geom IS NOT NULL
  AND ST_DWithin(geom, ST_Transform(ST_SetSRID(ST_MakePoint(8.6821, 50.1109), 4326), 25832), 5000);

-- 8. Locations that still need a human (unresolved / invalid) with the reason
SELECT source_id, geom_status, geom_note, location_text FROM iris_staging.signal_ingest
WHERE geom_status IN ('unresolved', 'invalid');
