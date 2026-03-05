import requests
import xml.etree.ElementTree as ET

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/refs/heads/main/epg_wib_sports.xml"
M3U_URL = "https://raw.githubusercontent.com/mimipipi22/lalajo/refs/heads/main/playlist25"

def main():
    print("Mengambil data EPG dan M3U...")
    try:
        epg_content = requests.get(EPG_URL).content
        m3u_text = requests.get(M3U_URL).text

        root = ET.fromstring(epg_content)
        
        with open("DAFTAR_MAPPING.txt", "w", encoding="utf-8") as f:
            f.write("="*50 + "\n")
            f.write("📋 DAFTAR ID CHANNEL DI EPG (Taruh di Sebelah KIRI)\n")
            f.write("="*50 + "\n")
            epg_ids = set()
            for ch in root.findall('channel'):
                epg_ids.add(ch.get('id'))
            
            # Format langsung siap copas untuk script utama
            for cid in sorted(epg_ids):
                f.write(f'    "{cid}": "TULIS_NAMA_M3U_DISINI",\n')

            f.write("\n\n" + "="*50 + "\n")
            f.write("📺 DAFTAR NAMA CHANNEL DI M3U (Taruh di Sebelah KANAN)\n")
            f.write("="*50 + "\n")
            
            m3u_names = set()
            for line in m3u_text.splitlines():
                if line.startswith("#EXTINF"):
                    # Ambil nama channel setelah koma terakhir
                    nama = line.split(',')[-1].strip()
                    m3u_names.add(nama)
                    
            for nama in sorted(m3u_names):
                if nama: # Abaikan yang kosong
                    f.write(f'{nama}\n')

        print("Selesai! File DAFTAR_MAPPING.txt berhasil dibuat.")
    except Exception as e:
        print(f"Terjadi kesalahan: {e}")

if __name__ == "__main__":
    main()
