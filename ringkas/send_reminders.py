"""Cek & kirim pengingat tenggat yang sudah jatuh tempo.

Dipanggil sebagai cron job no_agent (tanpa LLM) tiap beberapa menit.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path("/root/hackhathon")
sys.path.insert(0, str(PROJECT_DIR))

from ringkas.db import ambil_pengingat_jatuh_tempo, connect, tandai_pengingat_terkirim  # noqa: E402
from ringkas.telegram_client import baca_bot_token, kirim_pesan  # noqa: E402


def _format_pesan(row) -> str:
    baris = [f"⏰ Pengingat tenggat: {row['judul']}"]
    if row["detail"]:
        baris.append(row["detail"])
    return "\n".join(baris)


def main() -> None:
    token = baca_bot_token()
    sekarang = datetime.now(timezone.utc).isoformat()
    terkirim = 0
    with connect() as conn:
        due = ambil_pengingat_jatuh_tempo(conn, sekarang_utc=sekarang)
        for row in due:
            kirim_pesan(token, row["telegram_chat_id"], _format_pesan(row))
            tandai_pengingat_terkirim(conn, reminder_id=row["reminder_id"])
            terkirim += 1
    if terkirim:
        print(f"Terkirim {terkirim} pengingat.")
    # stdout kosong kalau tidak ada yang jatuh tempo -> silent tick (no_agent cron).


if __name__ == "__main__":
    main()
