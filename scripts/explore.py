import json
from harvester.client import OParlClient

KRONBERG = "https://kronberg.ratsinfomanagement.net/webservice/oparl/v1.1/system"
PBU = "https://oparl.politik-bei-uns.de/system"

with OParlClient(timeout=20) as c:
    # 1) Politik bei uns : les communes de Hesse (et Francfort s'il y est)
    system = c.get_system(PBU)
    for b in c.iter_objects(system["body"], max_pages=50):
        ags = str(b.get("ags") or "")
        if ags.startswith("06") or "Frankfurt" in str(b.get("name")):
            print("PBU:", b.get("name"), ags, b["id"])

    # 2) Kronberg : voir 2 documents (Paper) en entier
    system = c.get_system(KRONBERG)
    body = next(c.iter_objects(system["body"]))
    print("URL des papers :", body.get("paper"))
    for i, p in enumerate(c.iter_objects(body["paper"], max_pages=1)):
        print(json.dumps(p, ensure_ascii=False, indent=2)[:1500])
        if i == 1:
            break