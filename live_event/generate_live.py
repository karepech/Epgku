import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import re
import gzip
import io

# ==========================================
# KONFIGURASI LINK & FILE
# ==========================================
EPG_URL = "https://epg.pw/xmltv/epg.xml"
M3U_URL = "https://raw.githubusercontent.com/mimipipi22/lalajo/refs/heads/main/playlist25"
OUTPUT_FILE = "live_events.m3u"
LINK_STANDBY = "https://bwifi.my.id/live.mp4"

# 1. KATA KUNCI BLOKIR
REPLAY_KEYWORDS = ["highlight", "replay", "classic", "best of", "re-run", "siaran ulang", "magazine", "preview", "review", "delay"]

# 2. KATA KUNCI OLAHRAGA (TANPA 'VS')
TARGET_SPORTS = ["motogp", "moto2", "moto3", "badminton", "bwf", "futsal", "voli", "volley", "basket", "nba", "fiba"]

# 3. KATA KUNCI CHANNEL (HANYA CHANNEL SPORTS RESMI YANG DITERIMA)
SPORTS_CHANNELS = ["sport", "bein", "spotv", "champions", "premier", "euro", "hub", "arena"]

def is_sports_channel(channel_name):
    """Filter untuk membuang MNCTV, GTV, RCTI, dll"""
    if not channel_name: return False
    return any(k in channel_name.lower() for k in SPORTS_CHANNELS)

def is_fresh_live(title):
    """Filter judul anti-replay dan harus Live murni"""
    if not title: return False
    t = title.lower()
    if any(k in t for k in REPLAY_KEYWORDS): return False
    return bool(re.search(r'\bvs\b', t)) or any(sport in t for sport in TARGET_SPORTS)

def main():
    print("1. Download EPG Asli dari epg.pw...")
    try:
        r = requests.get(EPG_URL, timeout=60)
        r.raise_for_status()
        content = r.content
        if content[:2] == b'\x1f\x8b':
            content = gzip.GzipFile(fileobj=io.BytesIO(content)).read()
        root = ET.fromstring(content)
    except Exception as e:
        print(f"❌ Gagal memuat EPG: {e}")
        return

    # FILTER CHANNEL: Hanya ambil jika nama channelnya mengandung "sport", "bein", "spotv", dll
    epg_channels_dict = {}
    for ch in root.findall("channel"):
        ch_name = ch.findtext("display-name")
        if ch_name and is_sports_channel(ch_name.strip()):
            epg_channels_dict[ch.get("id")] = ch_name.strip()

    print("2. Mencari Acara LIVE Murni...")
    now_wib = datetime.utcnow() + timedelta(hours=7)
    live_events = {} 

    for prog in root.findall("programme"):
        start_str, stop_str = prog.get("start"), prog.get("stop")
        if not start_str or not stop_str: continue

        try:
            # Langsung konversi dari UTC ke WIB
            start_wib = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S") + timedelta(hours=7)
            stop_wib = datetime.strptime(stop_str[:14], "%Y%m%d%H%M%S") + timedelta(hours=7)
        except ValueError: continue

        # Pastikan acara SEDANG tayang saat ini (H-5 menit)
        if start_wib - timedelta(minutes=5) <= now_wib <= stop_wib:
            ch_id = prog.get("channel")
            ch_name_epg = epg_channels_dict.get(ch_id)
            if not ch_name_epg: continue # Lewati jika bukan channel sports

            title = prog.findtext("title") or ""
            if is_fresh_live(title):
                # Kita hanya menyimpan SATU acara per channel agar tidak dobel di M3U
                live_events[ch_name_epg] = {"title": title, "start": start_wib, "stop": stop_wib}

    print("\n3. Membaca playlist25 Anda...")
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
                    
                    for epg_name, acr in live_events.items():
                        epg_clean = re.sub(r'[^a-z0-9]', '', epg_name.lower())
                        if epg_clean in m3u_name or m3u_name in epg_clean:
                            # Switch Link 2 menit sebelum main
                            link = stream_asli if now_wib >= acr["start"] - timedelta(minutes=2) else LINK_STANDBY
                            stat = "[LIVE]" if now_wib >= acr["start"] - timedelta(minutes=2) else "[STANDBY]"
                            jam = f"{acr['start'].strftime('%H:%M')}-{acr['stop'].strftime('%H:%M')} WIB"
                            
                            clean_extinf = re.sub(r'group-title="[^"]*"', '', extinf.rsplit(',', 1)[0]).strip()
                            f.write(f'{clean_extinf} group-title="🔴 LIVE SEKARANG", 🔴 {stat} {acr["title"]} ({jam})\n')
                            
                            for blk in [b for b in channel_block if not b.startswith("#EXTINF")]: f.write(blk + "\n")
                            f.write(link + "\n")
                            break # Hentikan loop agar tidak dobel
                channel_block = []
    print(f"SELESAI ✔ → {OUTPUT_FILE} bersih dari channel nyasar!")

if __name__ == "__main__":
    main()
