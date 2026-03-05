import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# ==========================================
# KONFIGURASI LINK & FILE
# ==========================================
EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/refs/heads/main/epg_wib_sports.xml"
M3U_URL = "https://raw.githubusercontent.com/mimipipi22/lalajo/refs/heads/main/playlist25"
OUTPUT_FILE = "live_events.m3u"

# ==========================================
# MAPPING CHANNEL BERDASARKAN "NAMA" EPG
# KIRI: <display-name> di EPG
# KANAN: Kata kunci pencarian di ujung M3U (setelah koma)
# ==========================================
MAPPING = {
    "beIN Sports 1": "BEIN SPORTS 1",
    "beIN Sports 2": "BEIN SPORTS 2",
    "beIN Sports 3": "BEIN SPORTS 3",
    "SPOTV": "SPOTV",
    "SPOTV 2": "SPOTV 2",
    # Tambahkan nama channel lain di sini
}

def get_wib_time():
    return datetime.utcnow() + timedelta(hours=7)

def main():
    print("1. Download EPG...")
    try:
        r_epg = requests.get(EPG_URL, timeout=30)
        r_epg.raise_for_status()
        root = ET.fromstring(r_epg.content)
    except Exception as e:
        print(f"Gagal memuat EPG: {e}")
        return

    # ========================================================
    # KAMUS BARU: Terjemahkan ID EPG menjadi NAMA EPG
    # ========================================================
    epg_channels_dict = {}
    for ch in root.findall("channel"):
        ch_id = ch.get("id")
        disp = ch.find("display-name")
        if disp is not None and disp.text:
            epg_channels_dict[ch_id] = disp.text.strip()

    print("2. Mencari acara LIVE berdasarkan Nama Channel...")
    now = get_wib_time()
    live_programs = {}

    for prog in root.findall("programme"):
        start_str = prog.get("start")
        stop_str = prog.get("stop")
        if not start_str or not stop_str: continue

        try:
            start_dt = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
            stop_dt = datetime.strptime(stop_str[:14], "%Y%m%d%H%M%S")
        except ValueError:
            continue

        if start_dt <= now <= stop_dt:
            ch_id = prog.get("channel")
            # Ambil NAMA channel dari kamus yang kita buat tadi
            ch_name_epg = epg_channels_dict.get(ch_id, "")
            title = prog.findtext("title") or "Live Event"

            # Cek apakah NAMA EPG ini ada di MAPPING kita
            for epg_key, m3u_keyword in MAPPING.items():
                # Bandingkan nama secara tidak case-sensitive
                if epg_key.lower() == ch_name_epg.lower():
                    live_programs[m3u_keyword] = title
                    print(f" -> LIVE DITEMUKAN: {title} (di {ch_name_epg})")
                    break

    print("3. Download M3U playlist25...")
    try:
        r_m3u = requests.get(M3U_URL, timeout=30)
        r_m3u.raise_for_status()
        m3u_lines = r_m3u.text.splitlines()
    except Exception as e:
        print(f"Gagal download M3U: {e}")
        return

    print("4. Membuat M3U Live Event (Mendukung DRM/Kodi/VLC)...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U name="🔴 LIVE SPORTS"\n')

        # List untuk mengumpulkan semua baris milik 1 channel
        channel_block = [] 
        
        for line in m3u_lines:
            line = line.strip()
            if not line: continue

            if line.startswith("#"):
                # Masukkan EXTINF, KODIPROP, EXTVLCOPT ke dalam blok
                channel_block.append(line)
            elif line.startswith("http"):
                stream_url = line
                
                # Cari baris mana yang merupakan #EXTINF di dalam blok
                extinf_idx = -1
                extinf_line = ""
                for i, tag in enumerate(channel_block):
                    if tag.startswith("#EXTINF"):
                        extinf_idx = i
                        extinf_line = tag
                        break
                
                if extinf_idx != -1:
                    # Cek apakah channel ini masuk jadwal Live
                    for keyword, event_title in live_programs.items():
                        if keyword.lower() in extinf_line.lower():
                            # Ganti judul acara di ujung baris EXTINF
                            parts = extinf_line.rsplit(',', 1)
                            if len(parts) == 2:
                                new_extinf = f'{parts[0]} group-title="🔴 LIVE EVENT",🔴 [LIVE] {event_title}'
                            else:
                                new_extinf = f'{extinf_line} 🔴 [LIVE] {event_title}'
                            
                            channel_block[extinf_idx] = new_extinf
                            
                            # Tulis SEMUA baris (termasuk DRM) ke file M3U baru
                            for block_line in channel_block:
                                f.write(block_line + "\n")
                            f.write(stream_url + "\n")
                            break
                            
                # Bersihkan blok untuk mulai membaca channel berikutnya
                channel_block = []

    print(f"SELESAI ✔ → {OUTPUT_FILE} siap digunakan!")

if __name__ == "__main__":
    main()
