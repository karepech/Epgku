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
    return datetime.utcnow() + timedelta(hours=7)

def get_logical_date(dt):
    if dt.hour < 6:
        return (dt - timedelta(days=1)).date()
    return dt.date()

def bersihkan_nama(nama):
    return re.sub(r'[^a-z0-9]', '', str(nama).lower())

def is_target_event(title):
    """
    FILTER SUPER KETAT:
    Hanya menerima jika ada kata 'vs' (Bola/Badminton) atau 'motogp'
    """
    if not title: return False
    t = title.lower()
    # Cek apakah ada kata 'vs' yang berdiri sendiri atau kata 'motogp'
    return re.search(r'\bvs\b', t) or "motogp" in t

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

    print("2. Mencari jadwal (Hanya 'vs' dan 'motogp')...")
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

        if stop_dt > now:
            ch_id = prog.get("channel")
            ch_name_epg = epg_channels_dict.get(ch_id, "")
            title = prog.findtext("title") or ""
            
            # CEK FILTER VS & MOTOGP
            if ch_name_epg and is_target_event(title):
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

    print("4. Meracik M3U Super Filter...")
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
                                kategori = "🔴 LIVE HARI INI" if acara["logical_date"] == hari_ini_logis else "📅 UPCOMING SPORTS"
                                
                                if now >= start_dt - timedelta(minutes=5):
                                    link_final = stream_url_asli
                                    status = "[LIVE]"
                                else:
                                    link_final = LINK_STANDBY
                                    status = "[STANDBY]"
                                    
                                jam = f"{start_dt.strftime('%H:%M')}-{acara['stop'].strftime('%H:%M')} WIB"
                                judul_final = f"🔴 {status} [{jam}] > {acara['title']}"
                                
                                parts = extinf_line.rsplit(',', 1)
                                if len(parts) == 2:
                                    info_kiri = re.sub(r'group-title="[^"]*"', '', parts[0]).strip()
                                    new_extinf = f'{info_kiri} group-title="{kategori}", {judul_final}'
                                    channel_block[extinf_idx] = new_extinf
                                
                                for block_line in channel_block:
                                    f.write(block_line + "\n")
                                f.write(link_final + "\n")
                            break 
                channel_block = []

    print(f"\nSELESAI ✔ → File '{OUTPUT_FILE}' sudah difilter sangat ketat!")

if __name__ == "__main__":
    main()
