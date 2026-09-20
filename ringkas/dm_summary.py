"""Ringkasan personal harian lewat DM.

Cron job no_agent -- untuk setiap grup aktif, kirim highlight personal ke
setiap member yang sudah /start (dm_aktif=1), disesuaikan dengan
konteks_personal mereka kalau ada (diisi lewat /konteks).
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path("/root/hackhathon")
sys.path.insert(0, str(PROJECT_DIR))

from ringkas.db import WIB, ambil_pesan, anggota_grup_dm_aktif, connect  # noqa: E402
from ringkas.telegram_client import baca_bot_token, baca_openai_key, kirim_pesan  # noqa: E402

MODEL = "gpt-5-mini"


def _ringkasan_personal(api_key: str, nama_grup: str, pesan_teks: str, nama_user: str, konteks: str | None) -> str:
    konteks_line = f"Konteks personal {nama_user}: {konteks}." if konteks else f"Belum ada konteks personal untuk {nama_user}."
    instructions = (
        f"Kamu 'Ringkas', kirim ringkasan personal singkat lewat DM untuk {nama_user}, "
        f"anggota grup Telegram '{nama_grup}'. Berdasarkan pesan-pesan grup hari ini di bawah, "
        f"tulis 2-4 kalimat ringkasan singkat berbahasa Indonesia yang menyorot bagian yang paling "
        f"relevan untuk orang ini. {konteks_line} Kalau ada konteks personal, prioritaskan info yang "
        "berkaitan dengannya (tapi tetap sebutkan tenggat/pengumuman penting lain kalau ada). "
        "JANGAN MENGARANG -- hanya pakai info dari pesan yang diberikan. Kalau tidak ada info yang "
        "relevan sama sekali, katakan itu apa adanya, singkat."
    )
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": pesan_teks},
        ],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"].strip()


def main() -> None:
    api_key = baca_openai_key()
    bot_token = baca_bot_token()

    now_utc = datetime.now(timezone.utc)
    now_wib = now_utc.astimezone(WIB)
    mulai_wib = now_wib.replace(hour=0, minute=0, second=0, microsecond=0)
    mulai_utc = mulai_wib.astimezone(timezone.utc).isoformat()
    sampai_utc = now_utc.isoformat()

    with connect() as conn:
        grup_aktif = [
            (r["id"], r["telegram_chat_id"], r["nama"])
            for r in conn.execute("SELECT id, telegram_chat_id, nama FROM groups WHERE aktif = 1")
        ]

    terkirim = 0
    for group_id, _chat_id, nama_grup in grup_aktif:
        with connect() as conn:
            pesan_penting = ambil_pesan(conn, group_id=group_id, sejak=mulai_utc, sampai=sampai_utc, tanpa_noise=True)
            anggota = anggota_grup_dm_aktif(conn, group_id=group_id)

        if not pesan_penting or not anggota:
            continue

        pesan_teks = "\n".join(f"{p['sender_nama'] or 'seseorang'}: {p['teks']}" for p in pesan_penting)

        for a in anggota:
            nama_user = a["nama_tampilan"] or "kamu"
            try:
                teks = _ringkasan_personal(
                    api_key, nama_grup or "grup", pesan_teks, nama_user, a["konteks_personal"]
                )
            except Exception as exc:
                print(f"[dm_summary] gagal buat ringkasan untuk {a['telegram_user_id']}: {exc}", flush=True)
                continue
            kirim_pesan(bot_token, a["telegram_user_id"], f"📬 Ringkasan personal hari ini ({nama_grup}):\n\n{teks}")
            terkirim += 1

    if terkirim:
        print(f"Ringkasan personal DM terkirim ke {terkirim} orang.")


if __name__ == "__main__":
    main()
