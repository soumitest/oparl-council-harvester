import requests, datetime

CANDIDATES = {
    "Glashütten": "https://rim.ekom21.de/glashuetten/webservice/oparl/v1.1/system",
    "Schmitten": "https://rim.ekom21.de/schmitten/webservice/oparl/v1.1/system",
    "Aarbergen": "https://rim.ekom21.de/aarbergen/webservice/oparl/v1.1/system",
    "Ortenberg": "https://rim.ekom21.de/ortenberg/webservice/oparl/v1.1/system",
}
KEYWORDS = ["rechenzentrum", "umspannwerk", "umspannanlage",
            "trafostation", "hochspannung", "datacenter", "data center"]
MAX_PAGES = 3

def get(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()

print("Test du", datetime.datetime.now().isoformat(timespec="seconds"))
for name, url in CANDIDATES.items():
    print("\n==", name)
    try:
        system = get(url)
        print("system OK, version:", system.get("oparlVersion"))
        bodies = get(system["body"])
        body_list = bodies.get("data", [])
        print("bodies:", len(body_list))
        for b in body_list:
            print(" body:", b.get("name"), "| paper:", b.get("paper"))
            purl, pages, total, hits = b.get("paper"), 0, 0, 0
            while purl and pages < MAX_PAGES:
                page = get(purl)
                for p in page.get("data", []):
                    total += 1
                    title = (p.get("name") or "").lower()
                    if any(k in title for k in KEYWORDS):
                        hits += 1
                        print("  HIT:", p.get("name"), "|", p.get("id"))
                purl = page.get("links", {}).get("next")
                pages += 1
            print(f"  papers scannés: {total}, hits: {hits}")
    except Exception as e:
        print("ERREUR:", type(e).__name__, e)