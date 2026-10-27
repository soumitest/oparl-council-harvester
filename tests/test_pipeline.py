from pathlib import Path

import pytest

from harvester.client import OParlClient
from harvester.fixtures import fixture_client
from harvester.pipeline import run

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "oparl"
SYSTEM = "https://ris.example.org/oparl/system"


def do_run(conn=None, systems=(SYSTEM,), prefixes=("06",)):
    with OParlClient(http=fixture_client(FIXTURES), max_retries=1, backoff=0) as c:
        return run(c, list(systems), list(prefixes), conn)


def test_dry_run_filters_dedupes_and_reports():
    rep = do_run()
    t = rep.to_dict()["totals"]
    assert t["papers_matched"] == 6          # paper/4 (Haushalt) is not a signal
    assert t["duplicates_in_run"] == 1       # paper/1 appears on both pages
    assert t["papers_malformed"] == 2
    s = rep.systems[0]
    assert s.bodies_skipped_by_ags == 1      # Berlin (AGS 11...) is never requested
    assert s.bodies_without_ags == 1
    assert rep.geom_status["resolved"] == 1 and rep.geom_status["invalid"] == 1


def test_failing_source_does_not_stop_other_sources():
    rep = do_run(systems=["https://dead.example.org/oparl/system", SYSTEM])
    assert rep.systems[0].status == "failed" and "404" in rep.systems[0].error
    assert rep.systems[1].papers_matched == 6


def test_no_geographic_filter_when_prefixes_empty():
    rep = do_run(prefixes=())
    assert rep.systems[0].bodies_skipped_by_ags == 0
    assert rep.systems[0].papers_matched == 7   # + the Berlin paper


# ---- integration: needs PostGIS. Set TEST_DATABASE_URL to run, otherwise skipped. ----
@pytest.fixture
def conn():
    import os
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    from harvester import db
    c = db.connect(url)
    db.init_schema(c)
    c.execute("TRUNCATE iris_staging.signal_ingest")
    c.commit()
    yield c
    c.close()


def test_rerun_is_idempotent(conn):
    first = do_run(conn)
    assert (first.inserted, first.updated, first.unchanged, first.db_errors) == (6, 0, 0, 0)
    second = do_run(conn)
    assert (second.inserted, second.updated, second.unchanged) == (0, 0, 6)
    assert conn.execute("SELECT count(*) FROM iris_staging.signal_ingest").fetchone()[0] == 6


def test_changed_source_updates_row_instead_of_duplicating(conn):
    do_run(conn)
    conn.execute("UPDATE iris_staging.signal_ingest SET title = 'old title' WHERE source_id LIKE '%/paper/1'")
    conn.commit()
    rep = do_run(conn)
    assert (rep.inserted, rep.updated, rep.unchanged) == (0, 1, 5)
    assert conn.execute("SELECT count(*) FROM iris_staging.signal_ingest").fetchone()[0] == 6


def test_stored_geometry_is_valid_25832_and_only_for_resolved(conn):
    do_run(conn)
    bad = conn.execute(
        "SELECT count(*) FROM iris_staging.signal_ingest WHERE geom IS NOT NULL AND "
        "(ST_SRID(geom) <> 25832 OR NOT ST_IsValid(geom))"
    ).fetchone()[0]
    assert bad == 0
    assert conn.execute("SELECT count(*) FROM iris_staging.signal_ingest WHERE geom IS NOT NULL").fetchone()[0] == 1
