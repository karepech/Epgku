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

# Link video Standby/Trailer Anda
LINK_STANDBY = "https://bwifi.my.id/live.mp4"

# Kata kunci SUPER KETAT (Hanya Bola, Badminton, dan MotoGP)
# Kata "vs" ditambahkan karena judul pertandingan bola/badminton sering kali hanya "Tim A vs Tim B"
SPORT_KEYWORDS = [
    # KATA KUNCI BOLA
    "football", "soccer", "liga", "league", "premier", "champions", "uefa", "fifa", 
    "afc", "bundesliga", "la liga", "serie a", "ligue 1", "eredivisie", "vs", "timnas", "fa cup", "copa",
    # KATA KUNCI BADMINTON
    "badminton", "bwf", "bulutangkis", "bulu tangkis", "thomas", "uber", "sudirman",
    # KATA KUNCI MOTOGP
    "motogp", "moto gp", "moto2", "moto3", "sprint race"
]

def get_wib_time():
    """Waktu saat ini di WIB (+7)"""
    return datetime.utcnow() + timedelta(hours=7)

def get_logical_date(dt):
    """Ganti hari dihitung mulai jam 06:00 WIB pagi"""
    if dt.hour < 6:
        return (dt - timedelta(days=1)).date()
    return dt.date()

def bersihkan_nama(nama):
    """Pembersih nama untuk Auto-Match channel"""
    return re.sub(r'[^a-z0-9]', '', str(nama).lower())

def is_target_sport(title):
    """Mengecek apakah JUDUL ACARA mengandung kata kunci target"""
    if not title: return False
    return any(k in title.lower() for k in SPORT_KEYWORDS)

def main():
    print("1. Download EPG...")
    try:
        r_epg = requests.get(EPG_URL, timeout=30)
        r_epg.raise_for_status()
        root = ET.fromstring(r_epg.content)
    except Exception as e:
        print(f"❌ Gagal memuat EPG: {e}")
        return

    epg_channels_dict = {}
    for ch in root.findall("channel"):
        ch_id = ch.get("id")
        disp = ch.find("display-name")
        if disp is not None and disp.text:
            epg_channels_dict[ch_id] = disp.text.strip()

    print("2. Mencari jadwal (Khusus Bola, Badminton, MotoGP)...")
    now = get_wib_time()
    hari_ini_logis = get_logical_date(now)
    epg_events = {} 

    for prog in root.findall("programme"):
        start_str = prog.get("start")
        stop_str = prog.get("stop")
        if not start_str or not stop_str: continue

        try:
            start_dt = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
            stop_dt = datetime.strptime(stop_str[:14], "%Y%m%d%H%M%S")
        except ValueError:
            continue

        # Filter 1: Ambil yang belum selesai (stop_dt > now)
        if stop_dt > now:
            ch_id = prog.get("channel")
            ch_name_epg = epg_channels_dict.get(ch_id, "")
            title = prog.findtext("title") or ""
            
            # Filter 2: HANYA CEK JUDULNYA SAJA dengan kata kunci super ketat
            if ch_name_epg and is_target_sport(title):
                event_info = {
                    "title": title,
                    "start": start_dt,
                    "stop": stop_dt,
                    "logical_date": get_logical_date(start_dt)
                }
                if ch_name_epg not in epg_events:
                    epg_events[ch_name_epg] = []
                epg_events[ch_name_epg].append(event_info)

    print("\n3. Download M3U playlist25...")
    try:
        r_m3u = requests.get(M3U_URL, timeout=30)
        r_m3u.raise_for_status()
        m3u_lines = r_m3u.text.splitlines()
    except Exception as e:
        print(f"❌ Gagal download M3U: {e}")
        return

    print("4. Meracik M3U (Auto-Match & Link Standby)...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U name="🔴 LIVE & UPCOMING SPORTS"\n')

        channel_block = [] 
        for line in m3u_lines:
            line = line.strip()
            if not line: continue

            if line.startswith("#"):
                channel_block.append(line)
            elif line.startswith("http"):
                stream_url_asli = line
                
                extinf_idx = -1
                extinf_line = ""
                for i, tag in enumerate(channel_block):
                    if tag.startswith("#EXTINF"):
                        extinf_idx = i
                        extinf_line = tag
                        break
                
                if extinf_idx != -1:
                    m3u_channel_name = extinf_line.split(',')[-1].strip()
                    nama_m3u_bersih = bersihkan_nama(m3u_channel_name)
                    
                    for epg_name, daftar_acara in epg_events.items():
                        nama_epg_bersih = bersihkan_nama(epg_name)
                        
                        if nama_epg_bersih and nama_m3u_bersih and (nama_epg_bersih in nama_m3u_bersih or nama_m3u_bersih in nama_epg_bersih):
                            
                            for acara in daftar_acara:
                                start_dt = acara["start"]
                                
                                # Kategori Hari
                                if acara["logical_date"] == hari_ini_logis:
                                    kategori = "🔴 LIVE HARI INI"
                                else:
                                    kategori = "📅 UPCOMING SPORTS"
                                    
                                # Logika Standby (Buka link asli 5 menit sebelum mulai)
                                if now >= start_dt - timedelta(minutes=5):
                                    link_final = stream_url_asli
                                    status_tayang = "[LIVE]"
                                else:
                                    link_final = LINK_STANDBY
                                    status_tayang = "[STANDBY]"
                                    
                                jam_mulai = start_dt.strftime("%H:%M")
                                jam_selesai = acara["stop"].strftime("%H:%M")
                                # Menambahkan WIB pada jam
                                judul = f"🔴 {status_tayang} [{jam_mulai}-{jam_selesai} WIB] {acara['title']}"
                                
                                parts = extinf_line.rsplit(',', 1)
                                if len(parts) == 2:
                                    info_kiri = re.sub(r'group-title="[^"]*"', '', parts[0]).strip()
                                    new_extinf = f'{info_kiri} group-title="{kategori}", {judul}'
                                else:
                                    new_extinf = f'{extinf_line} group-title="{kategori}", {judul}'
                                
                                channel_block[extinf_idx] = new_extinf
                                
                                # Tulis lisensi DRM dan link final
                                for block_line in channel_block:
                                    f.write(block_line + "\n")
                                f.write(link_final + "\n")
                            
                            break 
                            
                channel_block = []

    print(f"\nSELESAI ✔ → File '{OUTPUT_FILE}' sukses dibuat dan telah disaring ketat!")

if __name__ == "__main__":
    main()
