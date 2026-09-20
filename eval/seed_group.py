"""Generator data seed untuk evaluasi: grup simulasi realistis berbahasa
Indonesia (~250 pesan, ~20 item penting berlabel).

Bukan LLM-generated -- daftar kurator manual + variasi noise, supaya
deterministik dan bisa direproduksi (`python eval/seed_group.py` selalu
menghasilkan `eval/labels.json` yang sama).
"""

from __future__ import annotations

import json
import random
from pathlib import Path

random.seed(42)

OUT_PATH = Path(__file__).resolve().parent / "labels.json"

# Pesan "penting" -- kurasi manual, representasi 4 kategori item ringkasan.
# Setiap entri: (teks, jenis, label_penting=True selalu di sini)
PESAN_PENTING = [
    "Besok Senin upacara bendera, anak-anak pakai seragam lengkap ya",
    "Iuran kelas bulan ini 50.000, ditagih paling lambat Jumat",
    "Study tour ke Kebun Binatang tanggal 15 Oktober, biaya 150rb per anak",
    "Oke jadi sudah disepakati study tour ke Kebun Binatang ya bu/pak",
    "Ada yang tau jam berapa pulangnya kalau study tour?",
    "Besok libur karena tanggal merah",
    "PR matematika halaman 25-27 dikumpul hari Kamis",
    "Rapat wali murid hari Sabtu jam 9 pagi di aula sekolah",
    "Baju olahraga dipakai hari Selasa dan Kamis",
    "Uang kas kelas sudah terkumpul 2 juta, dipakai untuk apa ya?",
    "Sudah diputuskan uang kas dipakai buat acara perpisahan",
    "Vaksinasi booster untuk anak kelas 3 tanggal 20, bawa kartu vaksin",
    "Ekskul pramuka pindah jadwal jadi hari Jumat",
    "Siapa yang jadi among tamu di acara perpisahan?",
    "Bu Dewi jadi koordinator acara perpisahan, sudah disepakati semua",
    "Bayar SPP bulan ini paling lambat tanggal 10",
    "Ada razia gigi berlubang hari Rabu, bawa sikat gigi",
    "Kapan pembagian rapor semester ini?",
    "Pembagian rapor tanggal 22 Desember jam 8 pagi",
    "Foto kelas untuk buku tahunan hari Senin depan, pakai seragam batik",
]

# Pesan noise "mudah" -- cocok persis aturan is_noise (short-ack, emoji, dst).
NOISE_MUDAH = [
    "ok", "Ok", "siap", "SIAP", "noted", "aamiin", "makasih", "wkwk", "wkwkwk",
    "sip", "yoi", "gas", "lanjut", "hehe", "haha", "iya", "ya",
    "👍", "🙏", "😂😂😂", "🔥", "❤️", "👏👏", "😅",
    "Selamat pagi semuanya", "Met ultah ya!", "Selamat malam",
]

# Pesan noise "sulit" -- bentuknya beda dikit dari whitelist, tapi tetap
# semantiknya cuma basa-basi/noise -- ini kasus yang mungkin BOCOR (false
# negative rule-based filter), dicatat apa adanya di hasil eval.
NOISE_SULIT = [
    "sipp mantap",
    "wokeh siap",
    "trims banyak ya",
    "oke deh",
    "noted ya bu",
    "hehe iya betul",
    "aminn ya rabbal alamin",
]

# Kasus jebakan: mengandung frasa sapaan tapi sebenarnya membawa info penting
# -- pola ini BISA salah tertangkap noise oleh aturan greeting kita kalau
# tidak ada tanggal/uang eksplisit. Sengaja dimasukkan supaya eval jujur.
JEBAKAN_PENTING = [
    "Selamat pagi semua, jangan lupa besok upacara bendera ya",
]


def _bangun_pesan_penting() -> list[dict]:
    return [{"teks": t, "jenis": "text", "label_penting": True} for t in PESAN_PENTING + JEBAKAN_PENTING]


def _bangun_pesan_noise(jumlah: int) -> list[dict]:
    pool = NOISE_MUDAH + NOISE_SULIT
    hasil = []
    for _ in range(jumlah):
        teks = random.choice(pool)
        hasil.append({"teks": teks, "jenis": "text", "label_penting": False})
    # Beberapa stiker/gif tanpa caption.
    for _ in range(10):
        hasil.append({"teks": "", "jenis": random.choice(["sticker", "gif"]), "label_penting": False})
    return hasil


def buat_seed(total_pesan: int = 250) -> list[dict]:
    penting = _bangun_pesan_penting()
    noise = _bangun_pesan_noise(total_pesan - len(penting))
    semua = penting + noise
    random.shuffle(semua)
    for i, p in enumerate(semua):
        p["index"] = i
    return semua


def main() -> None:
    data = buat_seed()
    OUT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    jumlah_penting = sum(1 for p in data if p["label_penting"])
    print(f"Seed dibuat: {len(data)} pesan, {jumlah_penting} berlabel penting -> {OUT_PATH}")


if __name__ == "__main__":
    main()
