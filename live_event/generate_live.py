import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# ==========================================
# KONFIGURASI LINK & FILE
# ==========================================
# Mengambil EPG yang sudah diproses oleh script Anda sebelumnya
EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/refs/heads/main/epg_wib_sports.xml"
# Link playlist M3U sumber
M3U_URL = "https://raw.githubusercontent.com/mimipipi22/lalajo/refs/heads/main/playlist25"
# Nama file output (akan disimpan di folder yang sama dengan script ini)
OUTPUT_FILE = "live_events.m3u"

# ==========================================
# MAPPING CHANNEL
# Format: "ID/Nama di EPG" : "Kata kunci di M3U playlist25"
# ==========================================
MAPPING = {
    "BeIN Sports 1": "BEIN SPORT 1",
    "BeIN Sports 2": "BEIN SPORT 2",
    "BeIN Sports 3": "BEIN SPORT 3",
    "SPOTV": "SPOTV",
    "SPOTV 2": "SPOTV 2",
    # Tambahkan channel lain sesuai kebutuhan
}

def get_wib_time():
    # Ambil waktu UTC lalu tambah 7 jam untuk jadi WIB
    return datetime.utcnow() + timedelta(hours=7)

def main():
    print("1. Download EPG terbaru...")
    try:
        r_epg = requests.get(EPG_URL, timeout=30)
        r_epg.raise_for_status()
        root = ET.fromstring(r_epg.content)
    except Exception as e:
        print(f"Gagal download/parsing EPG: {e}")
        return

    print("2. Mencari acara yang sedang LIVE...")
    now = get_wib_time()
    live_programs = {}

    for prog in root.findall("programme"):
        start_str = prog.get("start")
        stop_str = prog.get("stop")
        if not start_str or not stop_str:
            continue

        try:
            # Format waktu EPG: YYYYMMDDHHMMSS
            start_dt = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
            stop_dt = datetime.strptime(stop_str[:14], "%Y%m%d%H%M%S")
        except ValueError:
            continue

        # Jika waktu sekarang (WIB) berada di antara jam mulai dan jam selesai
        if start_dt <= now <= stop_dt:
            ch_id = prog.get("channel")
            title = prog.findtext("title") or "Live Event"

            # Cocokkan dengan daftar MAPPING kita
            for epg_key, m3u_keyword in MAPPING.items():
                if epg_key.lower() in ch_id.lower():
                    live_programs[m3u_keyword] = title
                    print(f" -> LIVE: {title} (di {m3u_keyword})")
                    break

    print("3. Download M3U playlist25...")
    try:
        r_m3u = requests.get(M3U_URL, timeout=30)
        r_m3u.raise_for_status()
        m3u_lines = r_m3u.text.splitlines()
    except Exception as e:
        print(f"Gagal download M3U: {e}")
        return

    print("4. Membuat file M3U Live Event...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U name="🔴 LIVE SPORTS"\n')

        current_extinf = ""
        for line in m3u_lines:
            line = line.strip()
            if line.startswith("#EXTINF"):
                current_extinf = line
            elif line.startswith("http") and current_extinf:
                stream_url = line

                # Cek apakah channel ini sedang live
                for keyword, event_title in live_programs.items():
                    if keyword.lower() in current_extinf.lower():
                        # Buat baris baru khusus Live Event
                        f.write(f'#EXTINF:-1 group-title="🔴 LIVE EVENT", 🔴 [LIVE] {event_title}\n')
                        f.write(f'{stream_url}\n')
                        break

                current_extinf = ""

    print(f"SELESAI ✔ → {OUTPUT_FILE} berhasil dibuat!")

if __name__ == "__main__":
    main()
