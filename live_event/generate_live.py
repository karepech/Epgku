import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import re
import gzip
import io

# ==========================================
# KONFIGURASI LINK & FILE
# ==========================================
# EPG StarHub (Singapura) - Sangat akurat untuk beIN, SPOTV, Hub Sports, Premier
EPG_URL = "https://iptv-org.github.io/epg/guides/sg/starhubtvplus.com.epg.xml" 
M3U_URL = "https://raw.githubusercontent.com/mimipipi22/lalajo/refs/heads/main/playlist25"
OUTPUT_FILE = "live_events.m3u"
LINK_STANDBY = "https://bwifi.my.id/live.mp4"

# ==========================================
# PENGATURAN FILTER KETAT
# ==========================================
# 1. KATA KUNCI BLOKIR (Membuang Siaran Ulang/Magazine/Highlight)
REPLAY_KEYWORDS = ["highlight", "replay", "classic", "best of", "re-run", "siaran ulang", "magazine", "preview", "review", "delay", "encore"]

# 2. KATA KUNCI OLAHRAGA (Bola/Badminton pakai 'VS', sisanya daftar di bawah)
TARGET_SPORTS = ["motogp", "moto2", "moto3", "badminton", "bwf", "futsal", "voli", "volley", "basket", "nba", "fiba"]

# 3. KATA KUNCI CHANNEL (Hanya mengambil channel premium, abaikan TV Nasional)
SPORTS_CHANNELS = ["sport", "bein", "spotv", "champions", "premier", "euro", "hub", "arena"]

def is_sports_channel(channel_name):
    """Memastikan hanya channel olahraga resmi yang masuk (Hub Sports, beIN, SPOTV, dll)"""
    if not channel_name: return False
    return any(k in channel_name.lower() for k in SPORTS_CHANNELS)

def is_fresh_live(title):
    """Filter Judul: Harus Live Murni & Bukan Replay"""
    if not title: return False
    t = title.lower()
    if any(k in t for k in REPLAY_KEYWORDS): return False
    return bool(re.search(r'\bvs\b', t)) or any(sport in t for sport in TARGET_SPORTS)

def parse_to_wib(time_str):
    """
    FITUR CERDAS: Konversi otomatis zona waktu EPG ke WIB.
    StarHub biasanya SGT (+0800), script otomatis menguranginya 1 jam jadi WIB.
    """
    if not time_str: return None
    try:
        dt = datetime.strptime(time_str[:14], "%Y%m%d%H%M%S")
        if "+0700" in time_str:
            return dt # Sudah WIB
        elif "+0800" in time_str:
            return dt - timedelta(hours=1) # SGT (Singapura/WITA) ke WIB
        elif "+0900" in time_str:
            return dt - timedelta(hours=2) # WIT ke WIB
        else:
            return dt + timedelta(hours=7) # UTC ke WIB
    except:
        return None

def main():
    print(f"1. Download EPG StarHub (Singapura)...")
    try:
        r = requests.get(EPG_URL, timeout=60)
        r.raise_for_status()
        content = r.content
        if content[:2] == b'\x1f\x8b':
            content = gzip.GzipFile(fileobj=io.BytesIO(content)).read()
        root = ET.fromstring(content)
    except Exception as e:
        print(f"❌ Gagal memuat EPG StarHub: {e}")
        return

    # MENGAMBIL CHANNEL YANG LOLOS FILTER SAJA
    epg_channels_dict = {}
    for ch in root.findall("channel"):
        ch_name = ch.findtext("display-name")
        if ch_name and is_sports_channel(ch_name.strip()):
            epg_channels_dict[ch.get("id")] = ch_name.strip()

    print("2. Mencari Acara LIVE Murni & Sinkronisasi Jam ke WIB...")
    now_wib = datetime.utcnow() + timedelta(hours=7)
    live_events = {} 

    for prog in root.findall("programme"):
        start_str, stop_str = prog.get("start"), prog.get("stop")
        
        start_wib = parse_to_wib(start_str)
        stop_wib = parse_to_wib(stop_str)
        if not start_wib or not stop_wib: continue

        # LOGIKA TAYANG: Ambil jika acara sedang jalan atau H-5 menit
        if start_wib - timedelta(minutes=5) <= now_wib <= stop_wib:
            ch_id = prog.get("channel")
            ch_name_epg = epg_channels_dict.get(ch_id)
            if not ch_name_epg: continue

            title = prog.findtext("title") or ""
            if is_fresh_live(title):
                # Simpan 1 acara per channel agar tidak terjadi channel ganda di M3U
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
                    # Bersihkan nama untuk pencocokan otomatis
                    m3u_name = re.sub(r'[^a-z0-9]', '', extinf.split(',')[-1].lower())
                    
                    for epg_name, acr in live_events.items():
                        epg_clean = re.sub(r'[^a-z0-9]', '', epg_name.lower())
                        
                        # Pencocokan nama EPG StarHub dan nama di M3U Anda
                        if epg_clean in m3u_name or m3u_name in epg_clean:
                            # Auto-Switch: 2 menit sebelum mulai, ganti link standby ke link asli
                            if now_wib >= acr["start"] - timedelta(minutes=2):
                                link_final = stream_asli
                                status_tag = "[LIVE]"
                            else:
                                link_final = LINK_STANDBY
                                status_tag = "[STANDBY]"
                                
                            jam = f"{acr['start'].strftime('%H:%M')}-{acr['stop'].strftime('%H:%M')} WIB"
                            judul_baru = f"🔴 {status_tag} {acr['title']} ({jam})"
                            
                            # Tulis ulang baris EXTINF
                            clean_extinf = re.sub(r'group-title="[^"]*"', '', extinf.rsplit(',', 1)[0]).strip()
                            f.write(f'{clean_extinf} group-title="🔴 LIVE SEKARANG", {judul_baru}\n')
                            
                            # Tulis lisensi DRM (jika ada) dan link stream
                            for blk in [b for b in channel_block if not b.startswith("#EXTINF")]: 
                                f.write(blk + "\n")
                            f.write(link_final + "\n")
                            break # Hentikan loop agar rapi
                channel_block = []
    print(f"SELESAI ✔ → File '{OUTPUT_FILE}' sukses diperbarui dengan EPG StarHub!")

if __name__ == "__main__":
    main()
