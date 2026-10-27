import requests

KEYWORDS = ["frankfurt", "darmstadt", "wiesbaden", "offenbach", "hanau",
            "mainz", "rüsselsheim", "bad homburg", "hofheim", "oberursel",
            "langen", "dreieich", "maintal", "neu-isenburg", "rodgau"]

url = "https://dev.oparl.org/api/endpoints?page=1&limit=25"
while url:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    j = r.json()
    for e in j["data"]:
        title = e["title"].lower()
        if "ekom21" in e["url"] or any(k in title for k in KEYWORDS):
            print(e["title"], "|", e["url"])
    url = j["meta"].get("next")