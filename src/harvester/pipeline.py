"""Harvest -> filter -> normalize -> load."""
from __future__ import annotations

import logging
from typing import Callable, Iterator

import psycopg

from . import db
from .client import OParlClient, OParlError, PageStats
from .normalize import Record, normalize_paper
from .report import RunReport, SystemReport

log = logging.getLogger(__name__)


def _ags_allowed(ags: str | None, prefixes: list[str]) -> bool | None:
    """True/False if decidable, None if the body has no AGS."""
    if not prefixes:
        return True
    if not ags:
        return None
    return any(ags.startswith(p) for p in prefixes)


def harvest(
    client: OParlClient,
    system_urls: list[str],
    ags_prefixes: list[str],
    report: RunReport,
    modified_since: str | None = None,
    max_pages_per_body: int = 10_000,
) -> Iterator[Record]:
    """Yield matched Records. A failing source is reported, never fatal to the others."""
    seen: set[tuple[str, str]] = set()
    for system_url in system_urls:
        srep = SystemReport(url=system_url)
        report.systems.append(srep)
        try:
            system = client.get_system(system_url)
            bodies = list(client.iter_objects(system["body"]))
        except OParlError as exc:
            srep.status, srep.error = "failed", f"{type(exc).__name__}: {exc}"
            log.error("source %s failed: %s", system_url, srep.error)
            continue

        for body in bodies:
            srep.bodies_seen += 1
            ags = str(body["ags"]) if body.get("ags") is not None else None
            allowed = _ags_allowed(ags, ags_prefixes)
            if allowed is False:
                srep.bodies_skipped_by_ags += 1
                continue
            if allowed is None:
                srep.bodies_without_ags += 1  # cannot be filtered: kept and reported
            paper_url = body.get("paper")
            if not paper_url:
                srep.errors.append(f"body without 'paper' link: {body.get('id')}")
                continue

            stats = PageStats()
            params = {"modified_since": modified_since} if modified_since else None
            try:
                for paper in client.iter_objects(paper_url, params=params, stats=stats, max_pages=max_pages_per_body):
                    srep.papers_seen += 1
                    rec = normalize_paper(paper, system_url, body)
                    if not rec.matched_keywords:
                        srep.papers_no_match += 1
                        continue
                    key = (rec.source_system, rec.source_id)
                    if key in seen:
                        report.duplicates_in_run += 1
                        continue
                    seen.add(key)
                    srep.papers_matched += 1
                    report.geom_status[rec.geom_status] += 1
                    for issue in rec.issues:
                        report.issues[issue] += 1
                    if rec.geom_status in ("unresolved", "invalid"):
                        report.unresolved_locations.append(
                            {"source_id": rec.source_id, "geom_status": rec.geom_status, "note": rec.geom_note}
                        )
                    yield rec
            except OParlError as exc:
                srep.status = "partial"
                srep.errors.append(f"{paper_url}: {type(exc).__name__}: {exc}")
                log.error("papers of %s interrupted: %s", paper_url, exc)
            finally:
                srep.pages += stats.pages
                srep.papers_malformed += stats.malformed_items
                if stats.stopped_reason != "end":
                    srep.pagination_stopped.append(f"{paper_url}: {stats.stopped_reason}")


def run(
    client: OParlClient,
    system_urls: list[str],
    ags_prefixes: list[str],
    conn: psycopg.Connection | None,
    modified_since: str | None = None,
    max_pages_per_body: int = 10_000,
    on_record: Callable[[Record], None] | None = None,
) -> RunReport:
    report = RunReport(dry_run=conn is None)
    for rec in harvest(client, system_urls, ags_prefixes, report, modified_since, max_pages_per_body):
        if on_record:
            on_record(rec)
        if conn is None:
            continue
        try:
            outcome = db.upsert(conn, rec)
        except psycopg.Error as exc:
            report.db_errors += 1
            log.error("DB error on %s: %s", rec.source_id, exc)
            continue
        setattr(report, outcome, getattr(report, outcome) + 1)
    if conn is not None:
        conn.commit()
    return report
