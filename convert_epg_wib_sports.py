import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import os

EPG_URL = "https://epg.pw/xmltv/epg.xml"
OUTPUT_FILE = "epg_wib_sports.xml"

# DAFTAR KATA KUNCI SUDAH DIPERLENGKAP
SPORT_KEYWORDS = [
    "sport", "sports", "football", "soccer", "match",
    "liga", "league", "premier", "champions", "uefa",
    "fifa", "afc", "caf", "conmebol",
    "bundesliga", "la liga", "serie a", "ligue",
    "mls", "eredivisie", "bein", "spotv", "astro", "arena",
    "basket", "nba", "wnba",
    "motogp", "moto gp", "formula", "f1", "race", "sprint",
    "tennis", "badminton", "bwf",
    "volley", "volleyball", "vnl", "proliga",
    "ufc", "boxing", "mma", "smackdown",
    "wrestling", "golf", "pga",
    "cricket", "rugby", "nhl",
    "olympic", "sea games", "asian games"
]

def is_sport(text):
    if not text: return False
    t = text.lower()
    return any(k in t for k in SPORT_KEYWORDS)

def convert_to_wib(time_str):
    """
    Fungsi Cerdas: Membaca jam EPG, melihat zona waktunya (misal +0000 atau +0800), 
    mengonversinya ke zona netral, lalu memastikannya menjadi WIB (+0700).
    """
    if not time_str: return ""
    try:
        # Format XMLTV standar: YYYYMMDDHHMMSS +ZZZZ
        if len(time_str) >= 19 and ('+' in time_str or '-' in time_str):
            dt_str = time_str[:14]
            tz_str = time_str[15:20] # Contoh: +0000
            
            dt = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
            
            # Hitung offset waktu aslinya
            sign = 1 if tz_str[0] == '+' else -1
            hours = int(tz_str[1:3])
            mins = int(tz_str[3:5])
            offset_delta = timedelta(hours=sign*hours, minutes=sign*mins)
            
            # Ubah ke UTC murni dulu, lalu tambah 7 jam untuk WIB
            utc_dt = dt - offset_delta
            wib_dt = utc_dt + timedelta(hours=7)
            
            return wib_dt.strftime("%Y%m%d%H%M%S +0700")
        else:
            # Jika EPG tidak mencantumkan zona (asumsi UTC)
            dt = datetime.strptime(time_str[:14], "%Y%m%d%H%M%S")
            wib_dt = dt + timedelta(hours=7)
            return wib_dt.strftime("%Y%m%d%H%M%S +0700")
    except Exception:
        return time_str # Kembalikan asli jika gagal baca

def main():
    print(f"1. Mengunduh EPG Raksasa dari {EPG_URL} ...")
    try:
        r = requests.get(EPG_URL, stream=True, timeout=120)
        r.raise_for_status()
        
        with open("temp_epg.xml", "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    except Exception as e:
        print(f"❌ Gagal mendownload EPG: {e}")
        return

    print("2. Menyaring Olahraga & Mengonversi ke WIB (Hemat RAM)...")
    sport_channels = set()
    
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
            out.write('<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n')
            
            # Menggunakan iterparse agar RAM Github tidak meledak
            context = ET.iterparse("temp_epg.xml", events=("end",))
            for event, elem in context:
                if elem.tag == "channel":
                    name = elem.findtext("display-name")
                    if is_sport(name):
                        sport_channels.add(elem.get("id"))
                        out.write(ET.tostring(elem, encoding="unicode"))
                    elem.clear() # Hapus dari memori seketika
                    
                elif elem.tag == "programme":
                    title = elem.findtext("title")
                    channel_id = elem.get("channel")
                    
                    # Ambil jika ID channelnya olahraga ATAU judul acaranya olahraga
                    if channel_id in sport_channels or is_sport(title):
                        # Konversi waktu ke WIB (+0700)
                        start = elem.get("start")
                        stop = elem.get("stop")
                        if start: elem.set("start", convert_to_wib(start))
                        if stop: elem.set("stop", convert_to_wib(stop))
                        
                        out.write(ET.tostring(elem, encoding="unicode"))
                    elem.clear() # Hapus dari memori seketika
                    
            out.write('</tv>\n')
            
    except Exception as e:
        print(f"❌ Gagal memproses XML: {e}")
        
    finally:
        # Bersihkan file temp agar server lega
        if os.path.exists("temp_epg.xml"):
            os.remove("temp_epg.xml")

    print(f"\nSELESAI ✔ File [{OUTPUT_FILE}] berhasil dicetak dalam format WIB!")

if __name__ == "__main__":
    main()
