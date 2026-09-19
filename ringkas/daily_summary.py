"""Ringkasan harian otomatis untuk semua grup aktif.

Cron job no_agent -- tidak lewat sesi agent Hermes (yang tidak otomatis tahu
tanggal/jam saat ini), tapi panggil OpenAI langsung (structured output)
memakai kredensial dibaca dari .env, meniru persis logika `/ringkas` di
hermes/plugins/ringkas/__init__.py supaya hasilnya konsisten.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_DIR = Path("/root/hackhathon")
sys.path.insert(0, str(PROJECT_DIR))

from ringkas.db import (  # noqa: E402
    ambil_pengaturan_grup,
    ambil_pesan,
    connect,
    get_or_create_group,
    simpan_ringkasan,
    simpan_tenggat_dengan_pengingat,
    tambah_item,
)
from ringkas.telegram_client import baca_openai_key, baca_bot_token, kirim_pesan  # noqa: E402

WIB = timezone(timedelta(hours=7))
MODEL = "gpt-5-mini"

_ITEMS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "tipe": {"type": "string", "enum": ["pengumuman", "tenggat", "keputusan", "pertanyaan"]},
                    "judul": {"type": "string"},
                    "detail": {"type": "string"},
                    "due_date_wib": {"type": "string"},
                    "due_time_wib": {"type": "string"},
                    "source_msg_ids": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["tipe", "judul", "detail", "due_date_wib", "due_time_wib", "source_msg_ids"],
            },
        },
    },
    "required": ["items"],
}

_TIPE_KE_LABEL = {
    "pengumuman": "📢 Pengumuman",
    "tenggat": "⏰ Tenggat",
    "keputusan": "✅ Keputusan",
    "pertanyaan": "❓ Belum terjawab",
}


def _ekstrak_items(api_key: str, instructions: str, pesan_text: str) -> list[dict]:
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": pesan_text},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "ringkas_items", "schema": _ITEMS_SCHEMA, "strict": True},
        },
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    parsed = json.loads(data["choices"][0]["message"]["content"])
    return parsed.get("items", [])


def _ringkas_satu_grup(api_key: str, bot_token: str, chat_id: str) -> None:
    now_utc = datetime.now(timezone.utc)
    now_wib = now_utc.astimezone(WIB)
    mulai_wib = now_wib.replace(hour=0, minute=0, second=0, microsecond=0)
    mulai_utc = mulai_wib.astimezone(timezone.utc).isoformat()
    sampai_utc = now_utc.isoformat()

    with connect() as conn:
        group_id = get_or_create_group(conn, chat_id)
        pengaturan = ambil_pengaturan_grup(conn, group_id=group_id)
        pesan_penting = ambil_pesan(conn, group_id=group_id, sejak=mulai_utc, sampai=sampai_utc, tanpa_noise=True)
        total_row = conn.execute(
            "SELECT COUNT(*) AS c FROM messages WHERE group_id = ? AND created_at >= ? AND created_at < ?",
            (group_id, mulai_utc, sampai_utc),
        ).fetchone()
        jumlah_pesan = total_row["c"]

    nama_grup = pengaturan.get("nama") or "Grup"
    tanggal_str = now_wib.strftime("%d %B %Y")
    header = f"📋 Ringkasan Grup {nama_grup} — {tanggal_str}\n{jumlah_pesan} pesan hari ini, {len(pesan_penting)} yang penting."

    if not pesan_penting:
        markdown = f"{header}\nTidak ada info penting hari ini."
        with connect() as conn:
            group_id = get_or_create_group(conn, chat_id)
            simpan_ringkasan(
                conn, group_id=group_id, periode_mulai=mulai_utc, periode_selesai=sampai_utc,
                isi_markdown=markdown, jumlah_pesan=jumlah_pesan, jumlah_penting=0,
            )
        kirim_pesan(bot_token, chat_id, markdown)
        return

    valid_ids = {p["id"] for p in pesan_penting}
    baris_pesan = "\n".join(
        f"[id={p['id']}] [{p['created_at']}] {p['sender_nama'] or 'seseorang'}: {p['teks']}"
        for p in pesan_penting
    )
    hari_indo = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"][now_wib.weekday()]
    instructions = (
        "Kamu asisten yang meringkas obrolan grup Telegram berbahasa Indonesia. "
        f"Hari ini {hari_indo}, {now_wib.strftime('%Y-%m-%d')} (WIB). "
        "Ekstrak HANYA item yang benar-benar ada di pesan berikut ini -- JANGAN MENGARANG. "
        "Setiap item WAJIB punya source_msg_ids berisi id pesan (angka di dalam [id=...]) "
        "yang benar-benar mendasarinya. Kategori: 'pengumuman' (info umum), "
        "'tenggat' (ada tenggat waktu/deadline -- hitung due_date_wib (YYYY-MM-DD) dari "
        "ekspresi waktu di pesan relatif ke hari ini; kalau tidak bisa dipastikan, kosongkan "
        "due_date_wib dan pakai tipe 'pengumuman' saja), 'keputusan' (sudah diputuskan), "
        "'pertanyaan' (pertanyaan yang belum terjawab). Isi field yang tidak relevan dengan "
        "string kosong. Kalau tidak ada item pada suatu kategori, jangan buat entrinya."
    )

    try:
        items = _ekstrak_items(api_key, instructions, baris_pesan)
    except Exception as exc:
        kirim_pesan(bot_token, chat_id, f"{header}\n(Gagal membuat ringkasan otomatis: {exc})")
        return

    items_valid = []
    for item in items:
        ids = [i for i in item.get("source_msg_ids", []) if i in valid_ids]
        if not ids or not item.get("judul"):
            continue
        items_valid.append({**item, "source_msg_ids": ids})

    bagian: dict[str, list[str]] = {"pengumuman": [], "tenggat": [], "keputusan": [], "pertanyaan": []}
    for item in items_valid:
        tipe = item.get("tipe") if item.get("tipe") in bagian else "pengumuman"
        item["_tipe_final"] = tipe
        judul = item["judul"]
        if tipe == "tenggat" and item.get("due_date_wib"):
            label = item["due_date_wib"] + (f" {item['due_time_wib']} WIB" if item.get("due_time_wib") else "")
            bagian["tenggat"].append(f"{judul} — {label}")
        else:
            bagian[tipe].append(judul)

    blok = [header]
    for tipe, label in _TIPE_KE_LABEL.items():
        if bagian[tipe]:
            blok.append(label)
            blok.extend(f"• {b}" for b in bagian[tipe])
    if len(blok) == 1:
        blok.append("Tidak ada info penting hari ini.")
    markdown = "\n".join(blok)

    with connect() as conn:
        group_id = get_or_create_group(conn, chat_id)
        summary_id = simpan_ringkasan(
            conn, group_id=group_id, periode_mulai=mulai_utc, periode_selesai=sampai_utc,
            isi_markdown=markdown, jumlah_pesan=jumlah_pesan, jumlah_penting=len(pesan_penting),
        )
        for item in items_valid:
            if item["_tipe_final"] == "tenggat" and item.get("due_date_wib"):
                try:
                    simpan_tenggat_dengan_pengingat(
                        conn, group_id=group_id, summary_id=summary_id, judul=item["judul"],
                        detail=item.get("detail") or None, due_date_wib=item["due_date_wib"],
                        due_time_wib=item.get("due_time_wib", ""), source_msg_ids=item["source_msg_ids"],
                    )
                    continue
                except ValueError:
                    pass
            tambah_item(
                conn, group_id=group_id, summary_id=summary_id, tipe=item["_tipe_final"],
                judul=item["judul"], detail=item.get("detail") or None, due_at=None,
                source_msg_ids=item["source_msg_ids"],
            )

    kirim_pesan(bot_token, chat_id, markdown)


def main() -> None:
    api_key = baca_openai_key()
    bot_token = baca_bot_token()
    with connect() as conn:
        grup_aktif = [r["telegram_chat_id"] for r in conn.execute("SELECT telegram_chat_id FROM groups WHERE aktif = 1")]
    for chat_id in grup_aktif:
        _ringkas_satu_grup(api_key, bot_token, chat_id)
    print(f"Ringkasan harian terkirim untuk {len(grup_aktif)} grup.")


if __name__ == "__main__":
    main()
