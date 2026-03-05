import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import re

# ==========================================
# KONFIGURASI LINK & FILE
# ==========================================
EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/refs/heads/main/epg_wib_sports.xml"
M3U_URL = "https://raw.githubusercontent.com/mimipipi22/lalajo/refs/heads/main/playlist25"
OUTPUT_FILE = "live_events.m3u"
LINK_STANDBY = "https://bwifi.my.id/live.mp4"

# Filter untuk membuang siaran ulang yang sering nyasar di jadwal live
REPLAY_KEYWORDS = ["highlight", "replay", "classic", "best of", "re-run", "siaran ulang", "magazine", "preview", "review"]

def get_wib_time():
    """Mengambil jam server GitHub (UTC) lalu menjadikannya WIB (+7) agar cocok dengan EPG Anda"""
    return datetime.utcnow() + timedelta(hours=7)

def is_fresh_live(title):
    """
    FILTER KETAT:
    1. Buang semua yang mengandung kata Highlight/Replay.
    2. Harus mengandung kata 'vs' atau 'motogp'.
    """
    if not title: return False
    t = title.lower()
    
    if any(k in t for k in REPLAY_KEYWORDS):
        return False
        
    return re.search(r'\bvs\b', t) or "motogp" in t

def main():
    print("1. Membaca EPG WIB Anda...")
    try:
        r_epg = requests.get(EPG_URL, timeout=30)
        r_epg.raise_for_status()
        root = ET.fromstring(r_epg.content)
    except Exception as e:
        print(f"❌ Gagal memuat EPG: {e}")
        return

    epg_channels_dict = {ch.get("id"): ch.findtext("display-name").strip() 
                         for ch in root.findall("channel") if ch.findtext("display-name")}

    print("2. Mencari siaran LIVE SEKARANG (Tanpa Siaran Ulang)...")
    now = get_wib_time()
    live_events = {} 

    for prog in root.findall("programme"):
        start_str, stop_str = prog.get("start"), prog.get("stop")
        if not start_str or not stop_str: continue

        try:
            # Mengambil waktu langsung dari EPG Anda yang sudah format WIB
            start_dt = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
            stop_dt = datetime.strptime(stop_str[:14], "%Y%m%d%H%M%S")
        except ValueError: continue

        # LOGIKA: Ambil jika waktu SEKARANG berada di dalam rentang jam tayang (atau 5 menit sebelum tayang)
        if start_dt - timedelta(minutes=5) <= now <= stop_dt:
            title = prog.findtext("title") or ""
            
            # Cek apakah ini Live Bola/Badminton/MotoGP murni
            if is_fresh_live(title):
                ch_id = prog.get("channel")
                ch_name_epg = epg_channels_dict.get(ch_id, "")
                
                if ch_name_epg:
                    if ch_name_epg not in live_events: live_events[ch_name_epg] = []
                    live_events[ch_name_epg].append({"title": title, "start": start_dt, "stop": stop_dt})

    print("\n3. Membaca playlist25...")
    try:
        r_m3u = requests.get(M3U_URL, timeout=30)
        m3u_lines = r_m3u.text.splitlines()
    except: return

    print("4. Meracik M3U Khusus LIVE...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U name="🔴 PURE LIVE SPORTS"\n')
        channel_block = [] 
        for line in m3u_lines:
            if not (line := line.strip()): continue
            if line.startswith("#"): channel_block.append(line)
            elif line.startswith("http"):
                stream_asli = line
                extinf = next((t for t in channel_block if t.startswith("#EXTINF")), "")
                if extinf:
                    m3u_name = re.sub(r'[^a-z0-9]', '', extinf.split(',')[-1].lower())
                    for epg_name, daftar in live_events.items():
                        epg_name_clean = re.sub(r'[^a-z0-9]', '', epg_name.lower())
                        # Auto-Match Channel
                        if epg_name_clean in m3u_name or m3u_name in epg_name_clean:
                            for acr in daftar:
                                # Jika belum waktunya (misal masih 4 menit sebelum kick-off), pakai Standby
                                link = stream_asli if now >= acr["start"] - timedelta(minutes=2) else LINK_STANDBY
                                status_teks = "[LIVE]" if now >= acr["start"] - timedelta(minutes=2) else "[STANDBY]"
                                jam = f"{acr['start'].strftime('%H:%M')}-{acr['stop'].strftime('%H:%M')} WIB"
                                
                                # Timpa teks M3U
                                clean_extinf = re.sub(r'group-title="[^"]*"', '', extinf.rsplit(',', 1)[0]).strip()
                                f.write(f'{clean_extinf} group-title="🔴 LIVE SEKARANG", 🔴 {status_teks} {acr["title"]} ({jam})\n')
                                
                                # Tulis DRM (Kodi/VLC)
                                for blk in [b for b in channel_block if not b.startswith("#EXTINF")]: f.write(blk + "\n")
                                f.write(link + "\n")
                            break
                channel_block = []
    print(f"SELESAI ✔ → {OUTPUT_FILE} diperbarui!")

if __name__ == "__main__":
    main()
# ==========================================
# KONFIGURASI LINK & FILE
# ==========================================
EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/refs/heads/main/epg_wib_sports.xml"
M3U_URL = "https://raw.githubusercontent.com/mimipipi22/lalajo/refs/heads/main/playlist25"
OUTPUT_FILE = "live_events.m3u"
LINK_STANDBY = "https://bwifi.my.id/live.mp4"

# Kata kunci yang menandakan siaran ulang (Akan DIBUANG)
REPLAY_KEYWORDS = ["highlight", "replay", "classic", "best of", "re-run", "siaran ulang", "arsip", "magazine", "preview"]

def get_wib_time():
    """Waktu saat ini di WIB (+7)"""
    return datetime.utcnow() + timedelta(hours=7)

def is_fresh_live(title):
    """
    MEMASTIKAN INI LIVE ASLI:
    1. Harus mengandung 'vs' atau 'motogp'.
    2. Tidak boleh mengandung kata siaran ulang/highlight.
    """
    if not title: return False
    t = title.lower()
    
    # Cek apakah ada kata siaran ulang
    if any(k in t for k in REPLAY_KEYWORDS):
        return False
        
    # Cek apakah ini pertandingan (vs) atau MotoGP
    return re.search(r'\bvs\b', t) or "motogp" in t

def main():
    print("1. Download EPG...")
    try:
        r_epg = requests.get(EPG_URL, timeout=30)
        r_epg.raise_for_status()
        root = ET.fromstring(r_epg.content)
    except Exception as e:
        print(f"❌ Gagal: {e}")
        return

    epg_channels_dict = {ch.get("id"): ch.findtext("display-name").strip() 
                         for ch in root.findall("channel") if ch.findtext("display-name")}

    print("2. Mencari siaran LIVE ASLI (Tanpa Highlight/Replay)...")
    now = get_wib_time()
    live_events = {} 

    for prog in root.findall("programme"):
        start_str, stop_str = prog.get("start"), prog.get("stop")
        if not start_str or not stop_str: continue

        try:
            start_dt = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
            stop_dt = datetime.strptime(stop_str[:14], "%Y%m%d%H%M%S")
        except ValueError: continue

        # KRITERIA LIVE MURNI:
        # 1. Sedang tayang sekarang atau H-5 menit.
        # 2. Judul lolos filter is_fresh_live (Tidak ada kata 'highlight' dll).
        if start_dt - timedelta(minutes=5) <= now <= stop_dt:
            title = prog.findtext("title") or ""
            
            if is_fresh_live(title):
                ch_id = prog.get("channel")
                ch_name_epg = epg_channels_dict.get(ch_id, "")
                
                if ch_name_epg:
                    if ch_name_epg not in live_events: live_events[ch_name_epg] = []
                    live_events[ch_name_epg].append({"title": title, "start": start_dt, "stop": stop_dt})

    print("\n3. Download M3U & Sinkronisasi...")
    try:
        r_m3u = requests.get(M3U_URL, timeout=30)
        m3u_lines = r_m3u.text.splitlines()
    except: return

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U name="🔴 PURE LIVE SPORTS"\n')
        channel_block = [] 
        for line in m3u_lines:
            if not (line := line.strip()): continue
            if line.startswith("#"): channel_block.append(line)
            elif line.startswith("http"):
                stream_asli = line
                extinf = next((t for t in channel_block if t.startswith("#EXTINF")), "")
                if extinf:
                    m3u_name = re.sub(r'[^a-z0-9]', '', extinf.split(',')[-1].lower())
                    for epg_name, daftar in live_events.items():
                        epg_name_clean = re.sub(r'[^a-z0-9]', '', epg_name.lower())
                        if epg_name_clean in m3u_name or m3u_name in epg_name_clean:
                            for acr in daftar:
                                # Jika sudah masuk menit pertandingan, pakai link asli, jika belum pakai standby.
                                link = stream_asli if now >= acr["start"] - timedelta(minutes=2) else LINK_STANDBY
                                jam = f"{acr['start'].strftime('%H:%M')}-{acr['stop'].strftime('%H:%M')} WIB"
                                
                                # Membersihkan group-title lama dan memasukkan ke kategori LIVE.
                                clean_extinf = re.sub(r'group-title="[^"]*"', '', extinf.rsplit(',', 1)[0]).strip()
                                f.write(f'{clean_extinf} group-title="🔴 LIVE SEKARANG", 🔴 [LIVE] {acr["title"]} ({jam})\n')
                                
                                # Tulis opsi DRM/Kodi.
                                for blk in [b for b in channel_block if not b.startswith("#EXTINF")]: f.write(blk + "\n")
                                f.write(link + "\n")
                            break
                channel_block = []
    print(f"SELESAI ✔ → {OUTPUT_FILE} hanya berisi siaran LIVE murni.")

if __name__ == "__main__":
    main()
