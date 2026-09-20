"""Penyaring noise berbasis aturan, dijalankan sebelum pesan masuk LLM.

Aturan (PLAN.md bagian 7):
- stiker/GIF tanpa teks -> noise
- pesan yang hanya berisi emoji -> noise
- pesan pendek standar ("ok", "siap", "noted", "aamiin", "makasih", "wkwk", dst) -> noise
- ucapan standar (ulang tahun, dst) -> noise, KECUALI memuat tanggal atau angka uang
"""

from __future__ import annotations

import re

# Kata/frasa pendek standar yang tidak mengandung informasi (dicocokkan setelah
# huruf kecil + tanda baca dibuang). Termasuk variasi ejaan umum.
_SHORT_ACK_WORDS = {
    "ok",
    "oke",
    "okay",
    "sip",
    "siap",
    "siappp",
    "noted",
    "nted",
    "aamiin",
    "amin",
    "aamin",
    "makasih",
    "makasi",
    "thanks",
    "thx",
    "ty",
    "terimakasih",
    "terima kasih",
    "wkwk",
    "wkwkwk",
    "wkwkwkwk",
    "haha",
    "hahaha",
    "hehe",
    "hehehe",
    "mantap",
    "mantul",
    "nice",
    "yoi",
    "yap",
    "yup",
    "iya",
    "ya",
    "oks",
    "gas",
    "lanjut",
}

# Kata pengisi tambahan (dipakai untuk cek frasa pendek "semua kata pengisi",
# lihat _is_filler_phrase) -- menangkap variasi ucapan singkat yang tidak
# persis cocok _SHORT_ACK_WORDS, mis. "sipp mantap", "wokeh siap", "noted ya bu".
_FILLER_WORDS = _SHORT_ACK_WORDS | {
    "sipp",
    "wokeh",
    "woke",
    "trims",
    "banyak",
    "deh",
    "sih",
    "bu",
    "pak",
    "kak",
    "min",
    "betul",
    "bener",
    "aminn",
    "rabbal",
    "alamin",
    "dong",
    "kok",
    "nih",
    "tuh",
    "loh",
    "lho",
}


def _is_filler_phrase(teks: str) -> bool:
    """True kalau SEMUA kata di pesan (maks 5 kata) ada di daftar kata pengisi."""
    kata = _normalize(teks).split()
    if not kata or len(kata) > 5:
        return False
    return all(k in _FILLER_WORDS for k in kata)

# Frasa ucapan standar yang jadi noise KECUALI ada tanggal/angka uang.
_GREETING_PATTERNS = [
    r"selamat ulang tahun",
    r"met ultah",
    r"happy birthday",
    r"selamat pagi",
    r"selamat siang",
    r"selamat sore",
    r"selamat malam",
    r"selamat menempuh hidup baru",
    r"barakallah",
    r"selamat atas",
]

# Tanggal (dd/mm, dd-mm, "5 januari", dst), penanda waktu relatif konkret
# ("besok", "lusa", nama hari), atau nominal uang (Rp, rb, ribu, juta, dst).
_DATE_OR_MONEY_RE = re.compile(
    r"(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)"  # 5/1, 05-01-2026
    r"|(\d{1,2}\s+(januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember))"
    r"|\b(besok|lusa|senin|selasa|rabu|kamis|jumat|sabtu|minggu)\b"
    r"|(rp\.?\s?\d)"  # Rp 50.000
    r"|(\d+\s?(rb|ribu|jt|juta))",
    re.IGNORECASE,
)

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "✀-➿"
    "️"
    "‍"
    "]+",
    re.UNICODE,
)


def _normalize(teks: str) -> str:
    stripped = teks.strip().lower()
    return re.sub(r"[^\w\s]", "", stripped, flags=re.UNICODE).strip()


def _is_emoji_only(teks: str) -> bool:
    stripped = teks.strip()
    if not stripped:
        return False
    without_emoji = _EMOJI_RE.sub("", stripped)
    return without_emoji.strip() == ""


def is_noise(teks: str, jenis: str = "text", kata_kunci_penting: list[str] | None = None) -> bool:
    """True kalau pesan dianggap noise (tidak perlu diringkas).

    `kata_kunci_penting` (hasil koreksi manual grup, mis. "iuran") membuat
    pesan yang menyinggung kata itu TIDAK PERNAH dianggap noise, apa pun
    aturan lain di bawah -- ini jalur H6 supaya koreksi pengguna berpengaruh
    ke ringkasan berikutnya.
    """
    teks = teks or ""

    if kata_kunci_penting:
        lower_teks = teks.lower()
        if any(kk.strip().lower() in lower_teks for kk in kata_kunci_penting if kk.strip()):
            return False

    # Stiker/GIF tanpa caption teks.
    if jenis in {"sticker", "gif"} and not teks.strip():
        return True

    if not teks.strip():
        return jenis != "text"

    if _is_emoji_only(teks):
        return True

    normalized = _normalize(teks)
    if normalized in _SHORT_ACK_WORDS:
        return True

    if _is_filler_phrase(teks):
        return True

    lower = teks.lower()
    is_greeting = any(re.search(pat, lower) for pat in _GREETING_PATTERNS)
    if is_greeting and not _DATE_OR_MONEY_RE.search(lower):
        return True

    return False
