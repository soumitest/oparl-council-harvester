"""Audit of the live sources: field coverage + titles containing broader terms.

Read-only. Takes a few minutes (reads every paper once). Paste the output into the README.
"""
from collections import Counter

from harvester.client import OParlClient
from harvester.filters import match_keywords

URLS = {
    "Kronberg": "https://kronberg.ratsinfomanagement.net/webservice/oparl/v1.1/system",
    "Schmitten": "https://rim.ekom21.de/schmitten/webservice/oparl/v1.1/system",
    "Glashuetten": "https://rim.ekom21.de/glashuetten/webservice/oparl/v1.1/system",
}
BROAD = ["rechen", "umspann", "trafo", "transformator", "hochspann", "kv", "server", "daten", "energie", "strom", "netz"]

with OParlClient(timeout=20) as c:
    for name, url in URLS.items():
        body = next(c.iter_objects(c.get_system(url)["body"]))
        keys, n, hits = Counter(), 0, {t: [] for t in BROAD}
        strict = []
        for p in c.iter_objects(body["paper"]):
            n += 1
            keys.update(p.keys())
            title = " ".join(str(p.get("name") or "").split())
            low = title.lower()
            for t in BROAD:
                if t in low:
                    hits[t].append(title[:110])
            if match_keywords(title):
                strict.append(title[:110])
        print(f"\n===== {name}: {n} papers")
        print("fields:", ", ".join(f"{k}={v}" for k, v in sorted(keys.items())))
        print("strict matches:", strict or "none")
        for t, titles in hits.items():
            print(f"  '{t}': {len(titles)}")
            for x in titles[:5]:
                print("     -", x)
