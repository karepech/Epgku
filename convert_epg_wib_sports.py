import requests
from lxml import etree
from datetime import datetime, timedelta
import gzip
import io

EPG_URL = "https://epg.pw/xmltv/epg.xml"
OUTPUT_FILE = "epg_wib_sports.xml"

SPORT_KEYWORDS = [
    "sport", "sports", "football", "soccer", "match",
    "liga", "league", "premier", "champions", "uefa",
    "fifa", "afc", "caf", "conmebol",
    "bundesliga", "la liga", "serie a", "ligue",
    "mls", "eredivisie",
    "basket", "nba", "wnba",
    "motogp", "moto gp", "formula", "f1", "race",
    "tennis", "badminton", "bwf",
    "volley", "volleyball",
    "ufc", "boxing", "mma",
    "wrestling", "golf", "pga",
    "cricket", "rugby", "nhl",
    "olympic", "sea games", "asian games"
]

def is_sport(text):
    if not text:
        return False
    t = text.lower()
    return any(k in t for k in SPORT_KEYWORDS)

def parse_utc_time(value):
    return datetime.strptime(value[:14], "%Y%m%d%H%M%S")

def format_wib_time(dt):
    return dt.strftime("%Y%m%d%H%M%S") + " +0700"

def main():
    print("Download EPG...")
    r = requests.get(EPG_URL, timeout=120)
    r.raise_for_status()

    content = r.content
    if content[:2] == b'\x1f\x8b':
        content = gzip.GzipFile(fileobj=io.BytesIO(content)).read()

    root = etree.fromstring(content)

    print("Filter channel SPORTS...")
    sport_channels = set()

    for ch in root.findall("channel"):
        name = ch.findtext("display-name")
        if is_sport(name):
            sport_channels.add(ch.get("id"))
        else:
            root.remove(ch)

    print("Filter programme + convert WIB...")
    for prog in root.findall("programme"):
        title = prog.findtext("title")
        channel_id = prog.get("channel")

        if channel_id not in sport_channels and not is_sport(title):
            root.remove(prog)
            continue

        # convert time
        start = prog.get("start")
        stop = prog.get("stop")

        if start:
            prog.set(
                "start",
                format_wib_time(parse_utc_time(start) + timedelta(hours=7))
            )

        if stop:
            prog.set(
                "stop",
                format_wib_time(parse_utc_time(stop) + timedelta(hours=7))
            )

    xml_bytes = etree.tostring(
        root,
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=True
    )

    with open(OUTPUT_FILE, "wb") as f:
        f.write(xml_bytes)

    print("SELESAI ✔ → epg_wib_sports.xml")

if __name__ == "__main__":
    main()
