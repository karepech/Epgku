import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# ==========================================
# KONFIGURASI LINK & FILE
# ==========================================
M3U_URL = "https://raw.githubusercontent.com/mimipipi22/lalajo/refs/heads/main/playlist25"
EPG_FILE = "epg_wib_sports.xml"
OUTPUT_M3U = "live_events.m3u"

# ==========================================
# MAPPING CHANNEL
# Format: "Nama Channel di EPG" : "Kata kunci di M3U playlist25"
# Sesuaikan jika ada nama yang berbeda
# ==========================================
MAPPING = {
    "BeIN Sports 1": "BEIN SPORT 1",
    "BeIN Sports 2": "BEIN SPORT 2",
    "BeIN Sports 3": "BEIN SPORT 3",
    "SPOTV": "SPOTV",
    "SPOTV 2": "SPOTV 2",
    # Tambahkan channel lain di sini
}

def get_wib_time():
    # Mengambil waktu UTC dan menambah 7 jam untuk WIB
    return datetime.utcnow() + timedelta(hours=7)

def parse_time(t_str):
    # Format waktu EPG: 20231025140000 +0700 (Ambil 14 digit pertama)
    return datetime.strptime(t_str[:14], "%Y%m%d%H%M%S")

def main():
    print("1. Membaca file EPG lokal...")
    try:
        tree = ET.parse(EPG_FILE)
        root = tree.getroot()
    except Exception as e:
        print(f"Gagal membaca EPG: {e}")
        return

    # Kumpulkan daftar nama channel dari EPG
    channels = {}
    for ch in root.findall('channel'):
        ch_id = ch.get('id')
        disp = ch.find('display-name')
        if disp is not None and disp.text:
            channels[ch_id] = disp.text

    now = get_wib_time()
    print(f"Waktu Sekarang (WIB): {now.strftime('%Y-%m-%d %H:%M:%S')}")

    print("2. Mencari pertandingan yang sedang LIVE...")
    live_programs = {}
    for prog in root.findall('programme'):
        start_str = prog.get('start')
        stop_str = prog.get('stop')
        if not start_str or not stop_str: continue

        start_dt = parse_time(start_str)
        stop_dt = parse_time(stop_str)

        # Cek apakah pertandingan sedang berlangsung saat ini
        if start_dt <= now <= stop_dt:
            ch_id = prog.get('channel')
            title_elem = prog.find('title')
            title = title_elem.text if title_elem is not None else "Event Tanpa Judul"
            ch_name = channels.get(ch_id, ch_id)

            # Cek apakah channel ini ada di MAPPING kita
            mapped_keyword = None
            for epg_key, m3u_keyword in MAPPING.items():
                if epg_key.lower() in ch_id.lower() or epg_key.lower() in ch_name.lower():
                    mapped_keyword = m3u_keyword
                    break

            if mapped_keyword:
                live_programs[mapped_keyword] = title
                print(f" -> LIVE DITEMUKAN: {title} (di {m3u_keyword})")

    print("3. Mendownload M3U playlist25...")
    r = requests.get(M3U_URL)
    m3u_lines = r.text.splitlines()

    print("4. Membuat live_events.m3u...")
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write('#EXTM3U name="🔴 LIVE SPORTS"\n')

        current_extinf = ""
        for line in m3u_lines:
            line = line.strip()
            if line.startswith("#EXTINF"):
                current_extinf = line
            elif line.startswith("http") and current_extinf:
                stream_url = line

                # Cocokkan link M3U dengan daftar acara LIVE
                for keyword, event_title in live_programs.items():
                    if keyword.lower() in current_extinf.lower():
                        # Buat baris baru dengan nama pertandingan
                        f.write(f'#EXTINF:-1 group-title="🔴 LIVE EVENT", 🔴 [LIVE] {event_title}\n')
                        f.write(f'{stream_url}\n')
                        break 
                
                current_extinf = ""

    print("SELESAI ✔ → live_events.m3u siap digunakan!")

if __name__ == "__main__":
    main()
