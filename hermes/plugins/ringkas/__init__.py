"""Plugin Hermes untuk Ringkas.

Dua tanggung jawab:

1. Menyimpan SETIAP pesan grup Telegram ke database lewat hook
   `pre_gateway_dispatch`, dan mengatur sendiri kapan bot boleh membalas
   (hanya saat di-mention/reply) -- menggantikan fitur observe/require_mention
   bawaan Hermes, karena fitur itu ternyata bekerja di level adapter Telegram
   SEBELUM pre_gateway_dispatch sempat fire untuk pesan yang tidak di-mention.

2. Perintah `/ringkas` -- memicu ringkasan manual untuk grup saat ini.
   Dikerjakan sebagai satu panggilan LLM terstruktur (`ctx.llm.complete_structured`),
   bukan lewat percakapan multi-turn, supaya formatnya selalu konsisten dan
   setiap item pasti berasal dari source_msg_ids yang benar-benar ada.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_DIR = Path("/root/hackhathon")
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from ringkas.db import (  # noqa: E402
    ambil_pengaturan_grup,
    ambil_pesan,
    connect,
    get_or_create_group,
    get_or_create_member,
    insert_message,
    simpan_ringkasan,
    simpan_tenggat_dengan_pengingat,
    tambah_item,
)
from ringkas.noise_filter import is_noise  # noqa: E402

BOT_USERNAME = os.environ.get("RINGKAS_BOT_USERNAME", "ringkasgrup_bot")
WIB = timezone(timedelta(hours=7))

# Chat_id grup dari pesan yang baru saja lewat pre_gateway_dispatch. Cukup
# variabel modul biasa (bukan ContextVar): gateway pada praktiknya memproses
# satu pesan sampai selesai (termasuk dispatch command) sebelum pesan
# berikutnya, dan /ringkas selalu didahului pesan itu sendiri lewat hook yang
# sama. Untuk skala uji coba single-group hackathon ini cukup aman.
_LAST_CHAT_ID: str | None = None
_LAST_CHAT_NAMA: str | None = None


def _pesan_mention_bot(event) -> bool:
    """Cek mention lewat entity Telegram asli (raw_message), BUKAN event.text.

    Hermes selalu membersihkan "@botusername" dari event.text sebelum hook
    pre_gateway_dispatch fire (lihat _clean_bot_trigger_text di adapter
    Telegram) -- jadi regex terhadap event.text tidak akan pernah match.
    Entity "mention" di pesan asli itu satu-satunya sumber yang bisa dipakai.
    """
    if getattr(event, "reply_to_is_own_message", False):
        return True
    raw = getattr(event, "raw_message", None)
    if raw is None:
        return False
    expected = f"@{BOT_USERNAME}".lower()
    for text_attr, entities_attr in (("text", "entities"), ("caption", "caption_entities")):
        text = getattr(raw, text_attr, None) or ""
        entities = getattr(raw, entities_attr, None) or []
        for ent in entities:
            etype = str(getattr(ent, "type", "")).split(".")[-1].lower()
            if etype != "mention":
                continue
            offset = getattr(ent, "offset", None)
            length = getattr(ent, "length", None)
            if offset is None or length is None:
                continue
            if text[offset : offset + length].strip().lower() == expected:
                return True
    return False


def _simpan_pesan_masuk(event, **kwargs):
    global _LAST_CHAT_ID, _LAST_CHAT_NAMA
    del kwargs
    source = getattr(event, "source", None)
    if source is None or getattr(source.platform, "value", source.platform) != "telegram":
        return None
    if source.chat_type not in ("group", "forum"):
        return None

    teks = event.text or ""
    jenis = event.message_type.value if getattr(event, "message_type", None) else "text"
    is_command = jenis == "command" or teks.strip().startswith("/")

    _LAST_CHAT_ID = str(source.chat_id)
    _LAST_CHAT_NAMA = source.chat_name

    if not is_command:
        try:
            noise = is_noise(teks, jenis=jenis)
            with connect() as conn:
                group_id = get_or_create_group(conn, str(source.chat_id), source.chat_name)
                member_id = get_or_create_member(
                    conn, str(source.user_id) if source.user_id else "unknown", source.user_name
                )
                insert_message(
                    conn,
                    group_id=group_id,
                    telegram_msg_id=str(event.message_id or event.platform_update_id),
                    sender_id=member_id,
                    teks=teks,
                    jenis=jenis,
                    is_noise=noise,
                    reply_to=event.reply_to_message_id,
                )
        except Exception as exc:  # pragma: no cover - defensif, jangan sampai gateway ikut error
            print(f"[ringkas] gagal simpan pesan: {exc}", flush=True)

    if is_command:
        return None  # command selalu boleh lewat, terlepas dari mention

    mentioned = _pesan_mention_bot(event)
    if not mentioned:
        return {"action": "skip", "reason": "ringkas-ambient-observed"}
    return None


_ITEMS_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tipe": {"type": "string", "enum": ["pengumuman", "tenggat", "keputusan", "pertanyaan"]},
                    "judul": {"type": "string"},
                    "detail": {"type": "string"},
                    "due_date_wib": {
                        "type": "string",
                        "description": "WAJIB diisi kalau tipe=tenggat DAN tanggal pastinya bisa dihitung: format YYYY-MM-DD (WIB). Kosongkan kalau tipe bukan tenggat, atau tanggal pastinya tidak bisa dipastikan dari pesan.",
                    },
                    "due_time_wib": {"type": "string", "description": "Jam WIB HH:MM kalau disebutkan, atau string kosong"},
                    "source_msg_ids": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["tipe", "judul", "source_msg_ids"],
            },
        },
    },
    "required": ["items"],
}

_TIPE_KE_JUDUL_BAGIAN = {
    "pengumuman": "📢 Pengumuman",
    "tenggat": "⏰ Tenggat",
    "keputusan": "✅ Keputusan",
    "pertanyaan": "❓ Belum terjawab",
}


def _handle_ringkas(raw_args, ctx=None):
    del raw_args
    if not _LAST_CHAT_ID:
        return "Perintah /ringkas cuma bisa dipakai di dalam grup."

    chat_id = _LAST_CHAT_ID
    now_utc = datetime.now(timezone.utc)
    now_wib = now_utc.astimezone(WIB)
    mulai_wib = now_wib.replace(hour=0, minute=0, second=0, microsecond=0)
    mulai_utc = mulai_wib.astimezone(timezone.utc).isoformat()
    sampai_utc = now_utc.isoformat()

    with connect() as conn:
        group_id = get_or_create_group(conn, chat_id, _LAST_CHAT_NAMA)
        pengaturan = ambil_pengaturan_grup(conn, group_id=group_id)
        pesan_penting = ambil_pesan(conn, group_id=group_id, sejak=mulai_utc, sampai=sampai_utc, tanpa_noise=True)
        total_row = conn.execute(
            "SELECT COUNT(*) AS c FROM messages WHERE group_id = ? AND created_at >= ? AND created_at < ?",
            (group_id, mulai_utc, sampai_utc),
        ).fetchone()
        jumlah_pesan = total_row["c"]

    nama_grup = pengaturan.get("nama") or _LAST_CHAT_NAMA or "Grup"
    tanggal_str = now_wib.strftime("%d %B %Y")
    header = f"📋 Ringkasan Grup {nama_grup} — {tanggal_str}\n{jumlah_pesan} pesan hari ini, {len(pesan_penting)} yang penting."

    if not pesan_penting:
        markdown = f"{header}\nTidak ada info penting hari ini."
        with connect() as conn:
            group_id = get_or_create_group(conn, chat_id, _LAST_CHAT_NAMA)
            simpan_ringkasan(
                conn,
                group_id=group_id,
                periode_mulai=mulai_utc,
                periode_selesai=sampai_utc,
                isi_markdown=markdown,
                jumlah_pesan=jumlah_pesan,
                jumlah_penting=0,
            )
        return markdown

    valid_ids = {p["id"] for p in pesan_penting}
    baris_pesan = "\n".join(
        f"[id={p['id']}] [{p['created_at']}] {p['sender_nama'] or 'seseorang'}: {p['teks']}"
        for p in pesan_penting
    )

    if ctx is None or not hasattr(ctx, "llm"):
        return f"{header}\n(Gagal membuat ringkasan: akses LLM plugin tidak tersedia.)"

    hari_indo = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"][now_wib.weekday()]
    try:
        result = ctx.llm.complete_structured(
            instructions=(
                "Kamu asisten yang meringkas obrolan grup Telegram berbahasa Indonesia. "
                f"Hari ini {hari_indo}, {now_wib.strftime('%Y-%m-%d')} (WIB). "
                "Ekstrak HANYA item yang benar-benar ada di pesan berikut ini -- JANGAN MENGARANG. "
                "Setiap item WAJIB punya source_msg_ids berisi id pesan (angka di dalam [id=...]) "
                "yang benar-benar mendasarinya. Kategori: 'pengumuman' (info umum), "
                "'tenggat' (ada tenggat waktu/deadline -- hitung due_date_wib (YYYY-MM-DD) dari "
                "ekspresi waktu di pesan relatif ke hari ini, mis. 'Kamis' -> tanggal Kamis "
                "terdekat ke depan; kalau tidak bisa dipastikan, kosongkan due_date_wib dan pakai "
                "tipe 'pengumuman' saja, jangan menebak), 'keputusan' (sudah diputuskan), "
                "'pertanyaan' (pertanyaan yang belum terjawab di akhir obrolan). "
                "Kalau tidak ada item pada suatu kategori, jangan buat entrinya."
            ),
            input=[{"type": "text", "text": baris_pesan}],
            json_schema=_ITEMS_SCHEMA,
            schema_name="ringkas.items",
            purpose="ringkas.manual_summary",
            temperature=0.0,
            max_tokens=1500,
        )
    except Exception as exc:
        return f"{header}\n(Gagal membuat ringkasan: {exc})"

    items = (result.parsed or {}).get("items", []) if result.content_type == "json" else []

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
    for tipe, label in _TIPE_KE_JUDUL_BAGIAN.items():
        if bagian[tipe]:
            blok.append(label)
            blok.extend(f"• {b}" for b in bagian[tipe])
    if len(blok) == 1:
        blok.append("Tidak ada info penting hari ini.")
    markdown = "\n".join(blok)

    with connect() as conn:
        group_id = get_or_create_group(conn, chat_id, _LAST_CHAT_NAMA)
        summary_id = simpan_ringkasan(
            conn,
            group_id=group_id,
            periode_mulai=mulai_utc,
            periode_selesai=sampai_utc,
            isi_markdown=markdown,
            jumlah_pesan=jumlah_pesan,
            jumlah_penting=len(pesan_penting),
        )
        for item in items_valid:
            if item["_tipe_final"] == "tenggat" and item.get("due_date_wib"):
                try:
                    simpan_tenggat_dengan_pengingat(
                        conn,
                        group_id=group_id,
                        summary_id=summary_id,
                        judul=item["judul"],
                        detail=item.get("detail"),
                        due_date_wib=item["due_date_wib"],
                        due_time_wib=item.get("due_time_wib", ""),
                        source_msg_ids=item["source_msg_ids"],
                    )
                    continue
                except ValueError:
                    pass  # due_date_wib tidak valid -- jatuh ke tambah_item biasa di bawah
            tambah_item(
                conn,
                group_id=group_id,
                summary_id=summary_id,
                tipe=item["_tipe_final"],
                judul=item["judul"],
                detail=item.get("detail"),
                due_at=None,
                source_msg_ids=item["source_msg_ids"],
            )

    return markdown


def _persona_ringkas(session_info: dict) -> str:
    """System prompt section: persona 'Ringkas' + aturan Q&A riwayat grup (H5).

    Dipanggil sekali per sesi baru. Kalau session_info tidak menyebut platform
    telegram, kosongkan supaya tidak mengganggu sesi CLI/lainnya di VPS yang
    sama.
    """
    if session_info.get("platform") != "telegram":
        return ""
    chat_id = _LAST_CHAT_ID or "(tidak diketahui)"
    nama_grup = _LAST_CHAT_NAMA or "grup ini"
    return (
        "Kamu adalah 'Ringkas', asisten peringkas grup chat Telegram -- BUKAN asisten pribadi umum. "
        f"Kamu sedang aktif di grup '{nama_grup}' dengan chat_id=\"{chat_id}\". "
        "Kalau di-mention dengan pertanyaan tentang riwayat/isi grup ini (siapa bilang apa, kapan, "
        "info tenggat/iuran/pengumuman, dst): WAJIB panggil tool cari_pesan atau ambil_pesan dulu "
        f"(pakai chat_id=\"{chat_id}\") untuk cari jawabannya di pesan yang BENAR ADA, baru jawab "
        "sambil menyebut sumbernya (mis. dari pesan siapa/kapan). JANGAN menjawab dari asumsi, dan "
        "JANGAN menawarkan untuk membuatkan pesan ke pihak lain -- tugasmu menjawab langsung dari "
        "data grup. Kalau setelah dicari tidak ketemu, jawab jujur dan singkat: "
        "\"Aku tidak menemukan info itu di grup.\" -- jangan mengarang. "
        "Balas dalam bahasa Indonesia, singkat dan langsung ke inti."
    )


def register(ctx):
    ctx.register_hook("pre_gateway_dispatch", _simpan_pesan_masuk)
    ctx.register_command(
        "ringkas",
        handler=lambda raw_args: _handle_ringkas(raw_args, ctx=ctx),
        description="Buat ringkasan manual pesan grup hari ini",
    )
    ctx.register_system_prompt_section(
        "ringkas.persona",
        _persona_ringkas,
        position="after_memory",
        max_chars=2000,
    )
