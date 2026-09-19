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

# Tanggal (dd/mm, dd-mm, "5 januari", dst) atau nominal uang (Rp, rb, ribu, juta, angka besar).
_DATE_OR_MONEY_RE = re.compile(
    r"(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)"  # 5/1, 05-01-2026
    r"|(\d{1,2}\s+(januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember))"
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


def is_noise(teks: str, jenis: str = "text") -> bool:
    """True kalau pesan dianggap noise (tidak perlu diringkas)."""
    teks = teks or ""

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

    lower = teks.lower()
    is_greeting = any(re.search(pat, lower) for pat in _GREETING_PATTERNS)
    if is_greeting and not _DATE_OR_MONEY_RE.search(lower):
        return True

    return False
