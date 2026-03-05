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

def get_wib_time():
    return datetime.utcnow() + timedelta(hours=7)

def bersihkan_nama(nama):
    """Menghapus spasi/simbol untuk mencocokkan nama channel"""
    return re.sub(r'[^a-z0-9]', '', str(nama).lower())

def main():
    print("1. Download EPG...")
    try:
        r_epg = requests.get(EPG_URL, timeout=30)
        r_epg.raise_for_status()
        root = ET.fromstring(r_epg.content)
    except Exception as e:
        print(f"❌ Gagal memuat EPG: {e}")
        return

    # Menerjemahkan ID EPG menjadi Nama EPG
    epg_channels_dict = {}
    for ch in root.findall("channel"):
        ch_id = ch.get("id")
        disp = ch.find("display-name")
        if disp is not None and disp.text:
            epg_channels_dict[ch_id] = disp.text.strip()

    print("2. Mencari acara LIVE untuk 12 Jam ke depan...")
    now = get_wib_time()
    batas_waktu = now + timedelta(hours=12) # Ambil jadwal sampai 12 jam ke depan
    
    # Format Dictionary: { "Nama Channel": ["Acara 1", "Acara 2"] }
    live_epg_channels = {} 

    for prog in root.findall("programme"):
        start_str = prog.get("start")
        stop_str = prog.get("stop")
        if not start_str or not stop_str: continue

        try:
            start_dt = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
            stop_dt = datetime.strptime(stop_str[:14], "%Y%m%d%H%M%S")
        except ValueError:
            continue

        # Filter: Sedang tayang SEKARANG atau AKAN TAYANG dalam 12 jam ke depan
        if now <= stop_dt and start_dt <= batas_waktu:
            ch_id = prog.get("channel")
            ch_name_epg = epg_channels_dict.get(ch_id, "")
            title = prog.findtext("title") or "Live Event"
            
            if ch_name_epg:
                # Format Jam Tayang menjadi [HH:MM - HH:MM WIB]
                jam_mulai = start_dt.strftime("%H:%M")
                jam_selesai = stop_dt.strftime("%H:%M")
                judul_lengkap = f"[{jam_mulai}-{jam_selesai} WIB] {title}"

                if ch_name_epg not in live_epg_channels:
                    live_epg_channels[ch_name_epg] = []
                live_epg_channels[ch_name_epg].append(judul_lengkap)

    if not live_epg_channels:
        print("ℹ️ Tidak ada siaran olahraga dalam 12 jam ke depan.")

    print("\n3. Download M3U playlist25...")
    try:
        r_m3u = requests.get(M3U_URL, timeout=30)
        r_m3u.raise_for_status()
        m3u_lines = r_m3u.text.splitlines()
    except Exception as e:
        print(f"❌ Gagal download M3U: {e}")
        return

    print("4. Mencocokkan Data & Membuat File M3U...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U name="🔴 LIVE SPORTS"\n')

        channel_block = [] 
        for line in m3u_lines:
            line = line.strip()
            if not line: continue

            if line.startswith("#"):
                channel_block.append(line)
            elif line.startswith("http"):
                stream_url = line
                
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
                    
                    # Cek apakah nama channel M3U ini punya jadwal di EPG
                    for epg_name, daftar_acara in live_epg_channels.items():
                        nama_epg_bersih = bersihkan_nama(epg_name)
                        
                        # Pencocokan otomatis (Auto-Match)
                        if nama_epg_bersih and nama_m3u_bersih and (nama_epg_bersih in nama_m3u_bersih or nama_m3u_bersih in nama_epg_bersih):
                            
                            # Jika cocok, buatkan baris M3U untuk SETIAP acara yang ada di channel ini
                            for acara in daftar_acara:
                                parts = extinf_line.rsplit(',', 1)
                                if len(parts) == 2:
                                    new_extinf = f'{parts[0]} group-title="🔴 LIVE EVENT",🔴 {acara}'
                                else:
                                    new_extinf = f'{extinf_line} 🔴 {acara}'
                                
                                channel_block[extinf_idx] = new_extinf
                                
                                # Tulis DRM (jika ada) dan info channel
                                for block_line in channel_block:
                                    f.write(block_line + "\n")
                                f.write(stream_url + "\n")
                            
                            print(f" -> MATCH: '{m3u_channel_name}' punya {len(daftar_acara)} acara live/upcoming.")
                            break # Lanjut ke channel M3U berikutnya
                            
                channel_block = []

    print(f"\nSELESAI ✔ → File '{OUTPUT_FILE}' sukses dibuat!")

if __name__ == "__main__":
    main()
