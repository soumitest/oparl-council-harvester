# OParl Council Harvester – Frankfurt / Rhine-Main (IRIS-SIG-20)

Harvests municipal council documents (OParl `Paper` objects) from public OParl APIs, keeps those that mention
**data centres or substations**, normalises them and loads them idempotently into
`iris_staging.signal_ingest` (PostgreSQL 16 / PostGIS 3.4, point geometry in EPSG:25832).

**Status at a glance**

| | |
|---|---|
| Live run (2026-10-27) | 3 sources, 2,119 papers read, 0 malformed, 0 errors |
| Genuine signals found | **0** (one false positive was found, analysed and excluded – see section 6) |
| Re-run behaviour | no duplicates (verified on live data and in automated tests) |
| Coordinates | the three sources publish **no** `location` on papers, so no geometry can be derived from them (section 7) |
| Tests | 39 run without a database, +3 PostGIS tests when `TEST_DATABASE_URL` is set |

---

## 1. Data source

Only public, unauthenticated OParl endpoints are used (descriptive User-Agent, no access-restriction bypass).
Availability was tested on **2026-10-27** with `python scripts/check_endpoints.py`:

| Source | OParl | Result (2026-10-27) |
|---|---|---|
| Kronberg im Taunus – `https://kronberg.ratsinfomanagement.net/webservice/oparl/v1.1/system` | 1.1 | OK – **used** |
| Schmitten im Taunus – `https://rim.ekom21.de/schmitten/webservice/oparl/v1.1/system` | 1.1 | OK – **used** |
| Glashütten – `https://rim.ekom21.de/glashuetten/webservice/oparl/v1.1/system` | 1.1 | OK – **used** |
| Politik bei uns (aggregator) – `https://oparl.politik-bei-uns.de/system` | 1.0 | OK, **not used**: its bodies are spread over Germany (e.g. Leipzig, Aachen, Wuppertal); no Hessian / Frankfurt body was found in the pages scanned (`scripts/explore.py`) |
| Rosbach v. d. Höhe – `https://www.rosbach.sitzung-online.de/bi/oparl/1.0/system.asp` | 1.0 | **Unavailable:** `OParlHTTPError: HTTP 404` (endpoint obsolete) |
| OParl Mirror – `https://mirror.oparl.org/system` | – | **Unavailable:** `getaddrinfo failed` (domain does not resolve) |

Frankfurt am Main's own council information system was **not found** as an OParl source among the tested endpoints.
Frankfurt's council runs its own parliamentary information system, PARLIS (`stvv.frankfurt.de/parlis`); a web search
on 2026-10-27 found no OParl interface for it. No HTML scraper was built, because the brief requires an OParl source
and lawful, documented access.
The Rhine-Main scope of this submission is therefore three Taunus municipalities (Hesse), used as the justified alternative.
Further candidates are listed in `scripts/exploration/` (endpoint search through `dev.oparl.org`).

## 2. Mapping (OParl `Paper` → `signal_ingest`)

| Column | Source | Notes |
|---|---|---|
| `source_system` | System URL | together with `source_id`: unique key |
| `source_id` | `Paper.id` | OParl object URL |
| `object_type` | constant `Paper` | |
| `title` | `Paper.name` (fallback `reference`) | whitespace and line breaks collapsed; NULL + `missing_title` if absent |
| `source_url` | `Paper.web` | human-readable link; NULL + `missing_web_url` if absent |
| `published_at` | `Paper.date` (fallback `created`) | UTC; date-only values are 00:00 UTC; unparsable → NULL + `invalid_date`; no date → `missing_date` |
| `matched_keywords` | title, reference, keywords, location text | see section 3 |
| `body_name`, `body_ags` | `Body.name`, `Body.ags` | geographic context (municipality) |
| `location_text` | `Paper.location` address fields | |
| `geom`, `geom_status`, `geom_note` | `Paper.location.geometry` (GeoJSON Point, lon/lat) | see section 3 |
| `raw` | the full Paper JSON | traceability |

## 3. Filters

**Domain filter** (`src/harvester/filters.py`). Case-insensitive substring match, so German compounds such as
*Rechenzentrumsstandort* match: Rechenzentrum/-zentren, data center/centre, Datenzentrum, Serverfarm,
Umspannwerk/-anlage/-station, Trafostation, Transformatorenstation, Schaltanlage, Hoch-/Höchstspannung, 110/380 kV.
Documented exclusion: "(Kommunales) Gebietsrechenzentrum" (the municipal IT provider ekom21), see section 6.

**Geographic filter.** (a) Source selection: Hessian municipalities of the Taunus / Rhine-Main area.
(b) AGS filter: bodies whose AGS (official municipality key) does not start with `OPARL_BODY_AGS_PREFIXES`
(default `06` = Hesse; Frankfurt am Main is `06412000`) are skipped. The three bodies used here publish **no AGS**,
so they cannot be filtered by AGS: they are kept and counted as `bodies_without_ags` in the report.

**Geometry (`geom_status`).**
- `resolved` – GeoJSON Point inside the Rhine-Main bounding box → WGS84 → EPSG:25832.
- `invalid` – malformed, NaN, out of range, or outside the bounding box (typical: swapped lon/lat). **Never stored as geometry**; the reason is in `geom_note`.
- `unresolved` – address only, non-point geometry, or location given as a URL reference. **No geocoder is used** (no unverified third-party service); the row is listed in the report.
- `none` – the paper carries no location.

A database constraint enforces `geom IS NOT NULL ⇔ geom_status = 'resolved'`.

## 4. Setup and run

Requirements: Python ≥ 3.12 and Docker.

**Windows (cmd):**
```bat
copy .env.example .env
docker compose up -d
python -m venv .venv
.venv\Scripts\activate.bat
pip install -e ".[dev]"

python -m harvester init-db
python -m harvester run
```

**Linux / macOS:**
```bash
cp .env.example .env
docker compose up -d
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python -m harvester init-db
python -m harvester run
```

Notes:
- PostGIS is published on host port **5433** (container port 5432) to avoid a clash with a locally installed PostgreSQL. Adjust `docker-compose.yml` and `DATABASE_URL` in `.env` if you prefer 5432.
- `docker-compose.yml` runs `sql/001_schema.sql` only when the volume is created. `init-db` is idempotent and can be run at any time; `docker compose down -v` starts from scratch.
- Credentials live only in `.env` (git-ignored); `.env.example` contains placeholders.

Options:

```
python -m harvester run --dry-run                           # fetch + filter + report, no database
python -m harvester run --since 2026-10-01T00:00:00+00:00   # incremental (OParl modified_since)
python -m harvester run --system <System URL> --max-pages 5 # one source, page limit per body
python -m harvester run --fixtures fixtures/oparl --system https://ris.example.org/oparl/system
                                                            # offline demo on synthetic data
```

Every run writes `reports/run_report.md` and `reports/run_report.json`.
Validation queries: `sql/validation_queries.sql`
(`docker compose exec -T db psql -U iris -d iris -f - < sql/validation_queries.sql`).

Configuration (`.env`): `DATABASE_URL`, `OPARL_SYSTEM_URLS` (comma-separated), `OPARL_BODY_AGS_PREFIXES`,
`HTTP_TIMEOUT_SECONDS`, `HTTP_MAX_RETRIES`.

## 5. Robustness and idempotency

- Pagination via `links.next`, loop detection, `--max-pages` guard; `modified_since` is sent on the first request only.
- Retries with exponential backoff on network errors, HTTP 429 and 5xx; other 4xx are not retried.
  (A `429` from Kronberg was observed once during the live audit and was absorbed by the retry.)
- HTTP 200 + OParl `Error` object, invalid JSON, wrong shape, empty or missing `data`, items without `id`: handled and counted.
- A failing source is reported as `failed` / `partial` and does not stop the others.
- Loading uses `INSERT … ON CONFLICT (source_system, source_id) DO UPDATE … WHERE <row differs>`:
  a re-run on unchanged data gives `inserted=0, updated=0, unchanged=N` and leaves `updated_at` untouched.
  Duplicates within one run are skipped and counted. Each row is saved in its own savepoint, so one bad row does not abort the run.

## 6. Results of the live run (2026-10-27)

Sources: Kronberg, Schmitten, Glashütten. Full report: `samples/live_run_report.md`.

| Source | Pages | Papers | Matched | Malformed |
|---|---|---|---|---|
| Kronberg im Taunus | 40 | 979 | 0 | 0 |
| Schmitten im Taunus | 20 | 497 | 0 | 0 |
| Glashütten | 26 | 643 | 0 | 0 |
| **Total** | 86 | **2,119** | **0** | **0** |

**False positive found and excluded.** A first run matched exactly one paper in Schmitten: the election of a
delegate to the assembly of *ekom21 – Kommunales Gebietsrechenzentrum Hessen* (the municipal IT provider).
It is not a data-centre project, so "Gebietsrechenzentrum" is now excluded (`EXCLUDE_PHRASES`, covered by tests).
Before the exclusion, this paper also served as a live idempotency check: the first run reported `inserted=1`,
the second `unchanged=1, inserted=0`. After the exclusion the row was removed and the run reports 0 matches.

**Recall check** (`scripts/audit.py`, output in `samples/live_audit.txt`): all 2,119 titles were searched for broader terms.

| Term in title | Kronberg | Schmitten | Glashütten | Assessment |
|---|---|---|---|---|
| umspann / trafo / transformator / hochspann | 0 | 0 | 0 | none |
| rechen | 0 | 2 | 5 | not data centres: "entsprechend…", the ekom21 election, hydraulic "Rechenbauwerk" (screen at a stream) |
| kv | 0 | 7 | 5 | not voltage: "Verkehrsverband", "EKVO" |
| server | 14 | 10 | 17 | "Wasserversorgung" (water supply) |
| daten | 3 | 0 | 3 | geodata infrastructure, data protection |
| energie / strom / netz | 11 | 12 | 7 | solar and energy-saving motions, tendering of electricity supply, broadband, and one grid-ownership company in Glashütten (electricity distribution network, not a substation or data-centre motion) |

Conclusion: no genuine data-centre or substation signal exists in the titles of these three sources;
the filter did not miss any title in the checked terms.

**Field coverage of the real `Paper` objects** (from `scripts/audit.py`):

| Field | Kronberg (979) | Schmitten (497) | Glashütten (643) |
|---|---|---|---|
| `name`, `web`, `created`, `modified`, `mainFile` | 100 % | 100 % | 100 % |
| `date` | 963 (98 %) | 497 (100 %) | 642 (99.8 %) |
| `location` | **0** | **0** | **0** |
| `keyword` | **0** | **0** | **0** |

## 7. Positive path: fixtures and samples

Because the live sources contain no signal and no coordinates, the full pipeline (filter → location → PostGIS) is demonstrated on
**synthetic** fixtures (`fixtures/oparl/`, fictional host `ris.example.org`). They contain a duplicate, malformed items,
an AGS-filtered body, a body without AGS, valid / swapped / address-only / reference locations and missing or invalid dates.

```
python -m harvester run --fixtures fixtures/oparl --system https://ris.example.org/oparl/system
```

- `samples/run_report.md` / `.json` – quality report of the fixture run (**synthetic data**)
- `samples/signal_ingest_sample.csv` – the resulting rows (1 `resolved`, 1 `invalid`, 2 `unresolved`, 2 `none`)
- `sql/validation_queries.sql` – duplicates, geometry validity, traceability, missing fields, spatial query

## 8. Tests

```bat
pytest
```
39 tests run without a database (client, pagination, retries, filters, normalisation, geometry, pipeline).
Three more tests need PostGIS and are skipped unless `TEST_DATABASE_URL` is set:

```bat
set TEST_DATABASE_URL=postgresql://iris:change_me@localhost:5433/iris
pytest
```
They check the idempotent re-run (`inserted=6`, then `unchanged=6`), the update of a changed source row without duplication,
and that stored geometries are valid points in EPSG:25832. **These tests truncate `iris_staging.signal_ingest`: use a throw-away database.**

## 9. Known limitations

- **No coordinates in the live sources.** None of the 2,119 papers has a `location`, so every live row would have `geom_status = 'none'`. The geometry path (GeoJSON Point → EPSG:25832, with invalid and unresolved cases) is verified on fixtures only; it has not been exercised on real data. It can be validated on any source that publishes locations.
- **ALLRIS not verified.** The brief names ALLRIS. I did not verify which council-information software the three sources run, so this README does not claim that they are ALLRIS.
- **Only paper metadata** (title, reference, keywords, address) is searched. The text of attached PDFs is not downloaded, so a signal appearing only inside a document is missed.
- **Frankfurt am Main itself is not covered** (no OParl source found); the three municipalities are small and rarely deal with data centres or substations, which explains the empty result.
- **AGS filter is inactive in practice**: the three bodies publish no AGS, so the geographic filter is the manual source selection.
- **`published_at` fallback:** `created` is used only when `date` is missing (16 papers in Kronberg, 1 in Glashütten). `created` may reflect the import into the information system rather than the publication date, so such values are less reliable.
- **Incremental retrieval** (`--since`) is implemented and tested against mocks, but it was not verified whether the live servers honour `modified_since`. If a server ignores it, the full list is returned and the upsert remains idempotent.
- Locations given only as an address or as a URL reference stay `unresolved`; no geocoding and no extra request per paper.
- Keyword matching can produce false positives (as with "Gebietsrechenzentrum"); `matched_keywords` makes every match reviewable.
- Only `Paper` objects are harvested (not `Meeting` / `AgendaItem`).
- Dates are stored in UTC.

## 10. Repository layout

```
src/harvester/   client.py (HTTP, retries, pagination) · filters.py · normalize.py · geo.py · db.py · pipeline.py · report.py · __main__.py (CLI)
sql/             001_schema.sql · validation_queries.sql
tests/           unit, pipeline and PostGIS tests
fixtures/oparl/  synthetic OParl responses for offline runs
samples/         fixture report, sample rows, live run report and live audit
scripts/         check_endpoints.py · explore.py · audit.py · exploration/
```
