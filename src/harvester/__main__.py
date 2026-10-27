"""CLI:  python -m harvester init-db | run [options]"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import db
from .client import OParlClient
from .config import Settings
from .fixtures import fixture_client
from .pipeline import run


def _load_dotenv() -> None:
    """Tiny .env loader (KEY=VALUE lines) so no extra dependency is needed."""
    import os

    path = Path(".env")
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    ap = argparse.ArgumentParser(prog="harvester", description="OParl council harvester (IRIS-SIG-20)")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="create schema/table (idempotent)")

    r = sub.add_parser("run", help="harvest, filter, normalize, load")
    r.add_argument("--system", action="append", help="OParl System URL (repeatable; default: OPARL_SYSTEM_URLS)")
    r.add_argument("--since", help="modified_since, ISO 8601 (incremental retrieval)")
    r.add_argument("--max-pages", type=int, default=10_000, help="page limit per body")
    r.add_argument("--dry-run", action="store_true", help="no database: only fetch, filter and report")
    r.add_argument("--fixtures", metavar="DIR", help="read from local fixtures instead of the network")
    r.add_argument("--report-dir", default="reports", help="where run_report.json / run_report.md are written")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()

    if args.cmd == "init-db":
        if not settings.database_url:
            sys.exit("DATABASE_URL is not set (see .env.example)")
        with db.connect(settings.database_url) as conn:
            db.init_schema(conn)
        print("schema iris_staging.signal_ingest ready")
        return 0

    systems = args.system or settings.oparl_system_urls
    if not systems:
        sys.exit("No OParl system URL: use --system or set OPARL_SYSTEM_URLS")
    http = fixture_client(args.fixtures) if args.fixtures else None
    conn = None
    if not args.dry_run:
        if not settings.database_url:
            sys.exit("DATABASE_URL is not set (or use --dry-run)")
        conn = db.connect(settings.database_url)
    try:
        with OParlClient(timeout=settings.http_timeout, max_retries=settings.http_max_retries, http=http) as client:
            report = run(client, systems, settings.body_ags_prefixes, conn, args.since, args.max_pages)
    finally:
        if conn is not None:
            conn.close()

    out = Path(args.report_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "run_report.json").write_text(report.to_json(), encoding="utf-8")
    (out / "run_report.md").write_text(report.to_markdown(), encoding="utf-8")
    print(report.to_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
