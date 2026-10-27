from harvester.client import OParlClient

CANDIDATES = {
    "Politik bei uns": "https://oparl.politik-bei-uns.de/system",
    "Kronberg im Taunus": "https://kronberg.ratsinfomanagement.net/webservice/oparl/v1.1/system",
    "Rosbach v. d. Höhe": "https://www.rosbach.sitzung-online.de/bi/oparl/1.0/system.asp",
    "Schmitten": "https://rim.ekom21.de/schmitten/webservice/oparl/v1.1/system",
    "Glashütten": "https://rim.ekom21.de/glashuetten/webservice/oparl/v1.1/system",
    "OParl Mirror": "https://mirror.oparl.org/system",
}


def check(name: str, url: str) -> None:
    try:
        with OParlClient(timeout=10, max_retries=1, backoff=0) as c:
            system = c.get_system(url)
            bodies = [b.get("name") for b in c.iter_objects(system["body"], max_pages=1)]
        print(f"OK    {name}: OParl {system.get('oparlVersion')} | bodies: {bodies[:5]}")
    except Exception as exc:
        print(f"FAIL  {name}: {type(exc).__name__}: {exc}")


for name, url in CANDIDATES.items():
    check(name, url)