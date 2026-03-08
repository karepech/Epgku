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
M3U_URL = "https://raw.githubusercontent.com/karepech/Karepetv/refs/heads/main/sports_combined.m3u5"
OUTPUT_FILE = "live_events.m3u"
LINK_STANDBY = "https://bwifi.my.id/live.mp4"

# ==========================================
# FILTER KATA KUNCI
# ==========================================
REPLAY_KEYWORDS = ["highlight", "replay", "classic", "best of", "re-run", "siaran ulang", "magazine", "preview", "review", "delay", "encore", "rpt", "repeat", "rewind"]
TARGET_SPORTS = ["motogp", "moto2", "moto3", "badminton", "bwf", "futsal", "voli", "volley", "basket", "nba", "fiba"]
SPORTS_CHANNELS = ["sport", "bein", "spotv", "champions", "premier", "euro", "hub", "arena", "astro"]

# DAFTAR LIGA EROPA UNTUK LOGIKA JAM (Buang jika tayang jam 06:00 - 18:59 WIB)
EURO_LEAGUES = ["premier", "laliga", "la liga", "bundesliga", "serie a", "ligue 1", "champions", "europa", "eredivisie", "scottish", "fa cup"]

def is_sports_channel(channel_name):
    if not channel_name: return False
    return any(k in channel_name.lower() for k in SPORTS_CHANNELS)

def is_fresh_live(prog, start_wib):
    if prog.find("previously-shown") is not None:
        return False

    title = prog.findtext("title") or ""
    if not title: return False
    t = title.lower()
    
    if any(k in t for k in REPLAY_KEYWORDS): return False

    # ATURAN JAM HARAM LIGA EROPA (06:00 Pagi - 18:59 Sore WIB)
    is_euro_league = any(liga in t for liga in EURO_LEAGUES)
    if is_euro_league:
        if 6 <= start_wib.hour < 19:
            return False 

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

    print("2. Mencari Acara LIVE Asli...")
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

            if is_fresh_live(prog, start_wib):
                title = prog.findtext("title") or ""
                live_events[ch_name_epg] = {"title": title, "start": start_wib, "stop": stop_wib}

    print("\n3. Membaca playlist M3U...")
    try:
        r_m3u = requests.get(M3U_URL, timeout=30)
        m3u_lines = r_m3u.text.splitlines()
    except Exception as e:
        print(f"❌ Gagal membaca M3U: {e}")
        return

    print("4. Meracik M3U (Strict Full-Block Mode)...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U name="🔴 PURE LIVE SPORTS"\n')
        
        channel_block = [] 
        jumlah_channel_dibuat = 0
        
        for line in m3u_lines:
            line = line.strip()
            if not line: continue
            
            # Abaikan tag EXTM3U global agar tidak masuk ke blok channel dan bikin error
            if line.upper().startswith("#EXTM3U"):
                continue

            if line.startswith("#"): 
                channel_block.append(line)
            else:
                # Jika baris ini bukan "#" (berarti ini link streaming), proses blok yang terkumpul
                stream_asli = line
                
                # Cari baris mana di dalam block yang merupakan #EXTINF
                extinf_idx = -1
                for i, tag in enumerate(channel_block):
                    if tag.upper().startswith("#EXTINF"):
                        extinf_idx = i
                        break
                        
                if extinf_idx != -1:
                    extinf = channel_block[extinf_idx]
                    
                    # Pemisahan nama channel menggunakan split(",", 1) agar aman dari nama yang mengandung koma
                    if "," in extinf:
                        extinf_attrs, m3u_name_asli = extinf.split(",", 1)
                        m3u_name_asli = m3u_name_asli.strip()
                    else:
                        extinf_attrs = extinf
                        m3u_name_asli = ""
                    
                    if is_sports_channel(m3u_name_asli):
                        m3u_name_clean = re.sub(r'[^a-z0-9]', '', m3u_name_asli.lower())
                        m3u_number = extract_channel_number(m3u_name_clean)
                        
                        for epg_name, acr in live_events.items():
                            epg_name_clean = re.sub(r'[^a-z0-9]', '', epg_name.lower())
                            epg_number = extract_channel_number(epg_name_clean)
                            
                            if (epg_name_clean in m3u_name_clean or m3u_name_clean in epg_name_clean) and (m3u_number == epg_number):
                                if now_wib >= acr["start"] - timedelta(minutes=2):
                                    link_final = stream_asli
                                    status_tag = "[LIVE]"
                                else:
                                    link_final = LINK_STANDBY
                                    status_tag = "[STANDBY]"
                                    
                                jam = f"{acr['start'].strftime('%H:%M')}-{acr['stop'].strftime('%H:%M')} WIB"
                                judul_baru = f"🔴 {status_tag} {acr['title']} ({jam})"
                                
                                # Hapus group-title lama dan masukkan yang baru tanpa merusak atribut lain (tvg-id, logo, dll)
                                clean_attrs = re.sub(r'\s*group-title="[^"]*"', '', extinf_attrs).strip()
                                
                                # Timpa/update baris EXTINF di dalam blok
                                channel_block[extinf_idx] = f'{clean_attrs} group-title="🔴 LIVE SEKARANG",{judul_baru}'
                                
                                # Tulis SATU BLOK UTUH TANPA TERKECUALI (termasuk tag ekstensi lain jika ada)
                                for blk in channel_block:
                                    f.write(blk + "\n")
                                f.write(link_final + "\n")
                                
                                jumlah_channel_dibuat += 1 
                                break 
                                
                # Reset blok untuk membaca channel selanjutnya
                channel_block = []
                
        # ==========================================
        # FITUR FALLBACK / ANTI-ERROR (JIKA KOSONG)
        # ==========================================
        if jumlah_channel_dibuat == 0:
            print("ℹ️ Tidak ada jadwal live, membuat Channel Info Fallback...")
            f.write('#EXTINF:-1 tvg-id="" tvg-name="INFO" tvg-logo="" group-title="ℹ️ INFORMASI", ℹ️ BELUM ADA SIARAN LIVE SAAT INI\n')
            f.write(f'{LINK_STANDBY}\n')

    print(f"SELESAI ✔ → {jumlah_channel_dibuat} siaran live ditemukan. (Jika 0, channel info dibuat).")

if __name__ == "__main__":
    main()
