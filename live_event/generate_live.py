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

def get_wib_time():
    """Waktu saat ini di WIB (+7)"""
    return datetime.utcnow() + timedelta(hours=7)

def get_logical_date(dt):
    """Hari baru dimulai jam 06:00 WIB"""
    if dt.hour < 6:
        return (dt - timedelta(days=1)).date()
    return dt.date()

def bersihkan_nama(nama):
    """Pembersih nama untuk Auto-Match channel"""
    return re.sub(r'[^a-z0-9]', '', str(nama).lower())

def is_target_event(title):
    """Filter ketat: Hanya 'vs' dan 'motogp'"""
    if not title: return False
    t = title.lower()
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

    print("2. Mencari jadwal (Filter: WIB Cycle 06.00-05.59)...")
    now = get_wib_time()
    hari_ini_logis = get_logical_date(now)
    live_events = {} 

    for prog in root.findall("programme"):
        start_str, stop_str = prog.get("start"), prog.get("stop")
        if not start_str or not stop_str: continue

        try:
            start_dt = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
            stop_dt = datetime.strptime(stop_str[:14], "%Y%m%d%H%M%S")
        except ValueError: continue

        # LOGIKA: Hanya ambil acara yang masuk siklus 'Hari Ini' (06:00 - 05:59)
        # DAN acara tersebut BELUM SELESAI (stop_dt > now)
        if get_logical_date(start_dt) == hari_ini_logis and stop_dt > now:
            ch_id = prog.get("channel")
            ch_name_epg = epg_channels_dict.get(ch_id, "")
            title = prog.findtext("title") or ""
            
            if ch_name_epg and is_target_event(title):
                if ch_name_epg not in live_events: live_events[ch_name_epg] = []
                live_events[ch_name_epg].append({"title": title, "start": start_dt, "stop": stop_dt})

    print("\n3. Download M3U & Meracik...")
    try:
        r_m3u = requests.get(M3U_URL, timeout=30)
        m3u_lines = r_m3u.text.splitlines()
    except: return

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U name="🔴 LIVE SPORTS TODAY"\n')
        channel_block = [] 
        for line in m3u_lines:
            if not (line := line.strip()): continue
            if line.startswith("#"): channel_block.append(line)
            elif line.startswith("http"):
                stream_asli = line
                extinf = next((t for t in channel_block if t.startswith("#EXTINF")), "")
                if extinf:
                    m3u_name = bersihkan_nama(extinf.split(',')[-1])
                    for epg_name, daftar in live_events.items():
                        if bersihkan_nama(epg_name) in m3u_name or m3u_name in bersihkan_nama(epg_name):
                            for acr in daftar:
                                # Switch link 5 menit sebelum kick-off
                                link = stream_asli if now >= acr["start"] - timedelta(minutes=5) else LINK_STANDBY
                                stat = "[LIVE]" if now >= acr["start"] - timedelta(minutes=5) else "[STANDBY]"
                                jam = f"{acr['start'].strftime('%H:%M')}-{acr['stop'].strftime('%H:%M')} WIB"
                                
                                clean_extinf = re.sub(r'group-title="[^"]*"', '', extinf.rsplit(',', 1)[0]).strip()
                                f.write(f'{clean_extinf} group-title="🔴 LIVE TODAY", 🔴 {stat} {acr["title"]} ({jam})\n')
                                for blk in [b for b in channel_block if not b.startswith("#EXTINF")]: f.write(blk + "\n")
                                f.write(link + "\n")
                            break
                channel_block = []
    print(f"SELESAI ✔ → {OUTPUT_FILE} diperbarui.")

if __name__ == "__main__":
    main()
