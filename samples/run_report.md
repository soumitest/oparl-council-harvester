# Ingestion report (2026-10-27T18:25:11+00:00)

| Metric | Value |
|---|---|
| papers_seen | 8 |
| papers_matched | 6 |
| papers_malformed | 2 |
| duplicates_in_run | 1 |
| inserted | 0 |
| updated | 0 |
| unchanged | 6 |
| db_errors | 0 |

## Geometry status

- invalid: 1
- none: 2
- resolved: 1
- unresolved: 2

## Data-quality issues (matched records)

- invalid_date: 1
- location_invalid: 1
- location_unresolved: 2
- missing_web_url: 1

## Sources

### https://ris.example.org/oparl/system — ok
- bodies: 3 seen, 1 skipped by AGS filter, 1 without AGS (kept)
- papers: 8 seen / 6 matched / 1 no match / 2 malformed (3 pages)

## Unresolved / invalid locations

- [unresolved] https://ris.example.org/oparl/paper/2 — address only, no coordinates in source (no geocoder used)
- [invalid] https://ris.example.org/oparl/paper/3 — outside expected area (lon/lat swapped?): lon=50.12, lat=8.68
- [unresolved] https://ris.example.org/oparl/paper/6 — location is a URL reference, not embedded
