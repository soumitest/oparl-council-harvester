"""Run report: what was fetched, kept, rejected, and why."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SystemReport:
    url: str
    status: str = "ok"            # ok | failed | partial
    error: str | None = None
    bodies_seen: int = 0
    bodies_skipped_by_ags: int = 0
    bodies_without_ags: int = 0
    pages: int = 0
    papers_seen: int = 0
    papers_malformed: int = 0
    papers_no_match: int = 0
    papers_matched: int = 0
    pagination_stopped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class RunReport:
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    dry_run: bool = False
    systems: list[SystemReport] = field(default_factory=list)
    duplicates_in_run: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    db_errors: int = 0
    geom_status: Counter = field(default_factory=Counter)
    issues: Counter = field(default_factory=Counter)  # missing_title, invalid_date, ...
    unresolved_locations: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at,
            "dry_run": self.dry_run,
            "totals": {
                "papers_seen": sum(s.papers_seen for s in self.systems),
                "papers_matched": sum(s.papers_matched for s in self.systems),
                "papers_malformed": sum(s.papers_malformed for s in self.systems),
                "duplicates_in_run": self.duplicates_in_run,
                "inserted": self.inserted,
                "updated": self.updated,
                "unchanged": self.unchanged,
                "db_errors": self.db_errors,
            },
            "geom_status": dict(self.geom_status),
            "data_quality_issues": dict(self.issues),
            "unresolved_or_invalid_locations": self.unresolved_locations,
            "systems": [s.__dict__ for s in self.systems],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_markdown(self) -> str:
        d = self.to_dict()
        t = d["totals"]
        lines = [
            f"# Ingestion report ({self.started_at}{', DRY RUN' if self.dry_run else ''})",
            "",
            "| Metric | Value |", "|---|---|",
            *[f"| {k} | {v} |" for k, v in t.items()],
            "",
            "## Geometry status", "",
            *([f"- {k}: {v}" for k, v in sorted(d["geom_status"].items())] or ["- (none)"]),
            "",
            "## Data-quality issues (matched records)", "",
            *([f"- {k}: {v}" for k, v in sorted(d["data_quality_issues"].items())] or ["- (none)"]),
            "",
            "## Sources", "",
        ]
        for s in self.systems:
            lines.append(f"### {s.url} — {s.status}")
            if s.error:
                lines.append(f"- error: `{s.error}`")
            lines.append(
                f"- bodies: {s.bodies_seen} seen, {s.bodies_skipped_by_ags} skipped by AGS filter, "
                f"{s.bodies_without_ags} without AGS (kept)"
            )
            lines.append(
                f"- papers: {s.papers_seen} seen / {s.papers_matched} matched / {s.papers_no_match} no match / "
                f"{s.papers_malformed} malformed ({s.pages} pages)"
            )
            for e in s.errors:
                lines.append(f"- error: `{e}`")
            for p in s.pagination_stopped:
                lines.append(f"- pagination stopped early: {p}")
            lines.append("")
        if self.unresolved_locations:
            lines += ["## Unresolved / invalid locations", ""]
            for u in self.unresolved_locations:
                lines.append(f"- [{u['geom_status']}] {u['source_id']} — {u['note']}")
        return "\n".join(lines) + "\n"
