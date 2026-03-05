import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import re
import gzip
import io

# ==========================================
# KONFIGURASI
# ==========================================
EPG_URL = "https://iptv-org.github.io/epg/guides/sg/starhubtvplus.com.epg.xml" 
M3U_URL = "https://raw.githubusercontent.com/mimipipi22/lalajo/refs/heads/main/playlist25"
OUTPUT_FILE = "live_events.m3u"
LINK_STANDBY = "https://bwifi.my.id/live.mp4"

REPLAY_KEYWORDS = ["highlight", "replay", "classic", "best of", "re-run", "siaran ulang", "magazine", "preview", "review", "delay", "encore", "rpt", "repeat", "rewind"]
TARGET_SPORTS = ["motogp", "moto2", "moto3", "badminton", "bwf", "futsal", "voli", "volley", "basket", "nba", "fiba"]
SPORTS_CHANNELS = ["sport", "bein", "spotv", "champions", "premier", "euro", "hub", "arena", "astro"]

# Daftar Liga Eropa untuk aturan "Jam Haram"
EURO_LEAGUES = ["premier", "laliga", "la liga", "bundesliga", "serie a", "ligue", "champions", "europa", "eredivisie", "scottish"]

def is_sports_channel(channel_name):
    if not channel_name: return False
    return any(k in channel_name.lower() for k in SPORTS_CHANNELS)

def is_fresh_live(prog, start_wib):
    """Filter Ekstra Ketat dengan Logika Waktu Benua Eropa"""
    if prog.find("previously-shown") is not None:
        return False

    title = prog.findtext("title") or ""
    if not title: return False
    t = title.lower()
    
    if any(k in t for k in REPLAY_KEYWORDS): return False

    # ATURAN JAM HARAM LIGA EROPA: 
    # Mustahil ada live Liga Eropa antara jam 06:00 Pagi sampai 17:00 Sore WIB
    is_daytime_wib = 6 <= start_wib.hour < 17
    if is_daytime_wib and any(liga in t for liga in EURO_LEAGUES):
        return False # Langsung tendang, ini 100% siaran ulang siang bolong

    return bool(re.search(r'\bvs\b', t)) or any(sport in t for sport in TARGET_SPORTS)

def parse_to_wib(time_str):
    if not time_str: return None
    try:
        dt = datetime.strptime(time_str[:14], "%Y%m%d%H%M%S")
        if "+0700" in time_str: return dt 
        elif "+0800" in time_str: return dt - timedelta(hours=1)
        elif "+0900" in time_str: return dt - timedelta(hours=2)
        else: return dt + timedelta(hours=7)
    except:
        return None

def extract_channel_number(name):
    """Mengekstrak angka dari nama channel untuk mencegah BeIN 1 masuk ke BeIN 2"""
    match = re.search(r'\d+', name)
    return match.group() if match else ""

def main():
    print("1. Download EPG...")
    try:
        r = requests.get(EPG_URL, timeout=60)
        r.raise_for_status()
        content = r.content
        if content[:2] == b'\x1f\x8b':
            content = gzip.GzipFile(fileobj=io.BytesIO(content)).read()
        root = ET.fromstring(content)
    except Exception as e:
        print(f"❌ Gagal: {e}")
        return

    epg_channels_dict = {}
    for ch in root.findall("channel"):
        ch_name = ch.findtext("display-name")
        if ch_name and is_sports_channel(ch_name.strip()):
            epg_channels_dict[ch.get("id")] = ch_name.strip()

    print("2. Mencari Acara LIVE Asli (Menyaring Replay Siang Hari)...")
    now_wib = datetime.utcnow() + timedelta(hours=7)
    live_events = {} 

    for prog in root.findall("programme"):
        start_wib = parse_to_wib(prog.get("start"))
        stop_wib = parse_to_wib(prog.get("stop"))
        if not start_wib or not stop_wib: continue

        if start_wib - timedelta(minutes=5) <= now_wib <= stop_wib:
            ch_id = prog.get("channel")
            ch_name_epg = epg_channels_dict.get(ch_id)
            if not ch_name_epg: continue

            # Masukkan start_wib ke filter untuk cek "Jam Haram"
            if is_fresh_live(prog, start_wib):
                title = prog.findtext("title") or ""
                # Mencegah duplikat acara di EPG yang sama
                live_events[ch_name_epg] = {"title": title, "start": start_wib, "stop": stop_wib}

    print("\n3. Membaca playlist25...")
    try:
        r_m3u = requests.get(M3U_URL, timeout=30)
        m3u_lines = r_m3u.text.splitlines()
    except: return

    print("4. Meracik M3U Tanpa Channel Kembar...")
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
                    m3u_name_clean = re.sub(r'[^a-z0-9]', '', extinf.split(',')[-1].lower())
                    m3u_number = extract_channel_number(m3u_name_clean)
                    
                    for epg_name, acr in live_events.items():
                        epg_name_clean = re.sub(r'[^a-z0-9]', '', epg_name.lower())
                        epg_number = extract_channel_number(epg_name_clean)
                        
                        # KUNCI ANGKA: Hanya cocokkan jika namanya mirip DAN angkanya sama persis!
                        if (epg_name_clean in m3u_name_clean or m3u_name_clean in epg_name_clean) and (m3u_number == epg_number):
                            
                            if now_wib >= acr["start"] - timedelta(minutes=2):
                                link_final = stream_asli
                                status_tag = "[LIVE]"
                            else:
                                link_final = LINK_STANDBY
                                status_tag = "[STANDBY]"
                                
                            jam = f"{acr['start'].strftime('%H:%M')}-{acr['stop'].strftime('%H:%M')} WIB"
                            judul_baru = f"🔴 {status_tag} {acr['title']} ({jam})"
                            
                            clean_extinf = re.sub(r'group-title="[^"]*"', '', extinf.rsplit(',', 1)[0]).strip()
                            f.write(f'{clean_extinf} group-title="🔴 LIVE SEKARANG", {judul_baru}\n')
                            
                            for blk in [b for b in channel_block if not b.startswith("#EXTINF")]: 
                                f.write(blk + "\n")
                            f.write(link_final + "\n")
                            break 
                channel_block = []
    print(f"SELESAI ✔ → Bersih dari siaran siang palsu & channel dobel!")

if __name__ == "__main__":
    main()
