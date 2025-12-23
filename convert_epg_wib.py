import requests
from lxml import etree
from datetime import datetime, timedelta
import gzip
import io

EPG_URL = "https://epg.pw/xmltv/epg.xml"
OUTPUT_FILE = "epg_wib.xml"

def parse_utc_time(value):
    # ambil YYYYMMDDHHMMSS
    return datetime.strptime(value[:14], "%Y%m%d%H%M%S")

def format_wib_time(dt):
    return dt.strftime("%Y%m%d%H%M%S") + " +0700"

def main():
    print("Download EPG dari epg.pw ...")
    response = requests.get(EPG_URL, timeout=120)
    response.raise_for_status()

    content = response.content

    # jika gzip
    if content[:2] == b'\x1f\x8b':
        content = gzip.GzipFile(fileobj=io.BytesIO(content)).read()

    root = etree.fromstring(content)

    print("Konversi waktu UTC ➜ WIB (+7 jam)...")
    for programme in root.findall("programme"):
        start = programme.get("start")
        stop = programme.get("stop")

        if start:
            start_dt = parse_utc_time(start) + timedelta(hours=7)
            programme.set("start", format_wib_time(start_dt))

        if stop:
            stop_dt = parse_utc_time(stop) + timedelta(hours=7)
            programme.set("stop", format_wib_time(stop_dt))

    xml_bytes = etree.tostring(
        root,
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=True
    )

    with open(OUTPUT_FILE, "wb") as f:
        f.write(xml_bytes)

    print("SELESAI ✔ → epg_wib.xml (WIB FIX)")

if __name__ == "__main__":
    main()
