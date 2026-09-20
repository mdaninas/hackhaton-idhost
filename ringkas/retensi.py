"""Hapus pesan mentah yang lebih tua dari retensi_hari tiap grup (harian).

Ringkasan & item TETAP disimpan -- cuma pesan mentah di tabel `messages`
yang dihapus (lihat PLAN.md bagian 5).
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_DIR = Path("/root/hackhathon")
sys.path.insert(0, str(PROJECT_DIR))

from ringkas.db import bersihkan_pesan_kadaluarsa, connect  # noqa: E402


def main() -> None:
    with connect() as conn:
        hasil = bersihkan_pesan_kadaluarsa(conn)
    if hasil:
        total = sum(hasil.values())
        print(f"Retensi: {total} pesan dihapus dari {len(hasil)} grup.")
    # stdout kosong kalau tidak ada yang dihapus -> silent tick (no_agent cron).


if __name__ == "__main__":
    main()
