"""Plugin Hermes untuk Ringkas.

Menyimpan SETIAP pesan grup Telegram ke database lewat hook
`pre_gateway_dispatch`, dan mengatur sendiri kapan bot boleh membalas
(hanya saat di-mention/reply) -- menggantikan fitur observe/require_mention
bawaan Hermes, karena fitur itu ternyata bekerja di level adapter Telegram
SEBELUM pre_gateway_dispatch sempat fire untuk pesan yang tidak di-mention.

Konsekuensinya justru plugin ini yang jadi satu-satunya penentu
diam-atau-balas, dan penyimpanan mentah (rule-based, tanpa LLM) dijamin
selalu jalan untuk setiap pesan grup yang masuk.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

PROJECT_DIR = Path("/root/hackhathon")
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from ringkas.db import connect, get_or_create_group, get_or_create_member, insert_message  # noqa: E402
from ringkas.noise_filter import is_noise  # noqa: E402

BOT_USERNAME = os.environ.get("RINGKAS_BOT_USERNAME", "ringkasgrup_bot")
_MENTION_RE = re.compile(rf"@{re.escape(BOT_USERNAME)}\b", re.IGNORECASE)


def _simpan_pesan_masuk(event, **kwargs):
    del kwargs
    source = getattr(event, "source", None)
    if source is None or getattr(source.platform, "value", source.platform) != "telegram":
        return None
    if source.chat_type not in ("group", "forum"):
        return None

    teks = event.text or ""
    jenis = event.message_type.value if getattr(event, "message_type", None) else "text"

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

    mentioned = bool(_MENTION_RE.search(teks)) or bool(getattr(event, "reply_to_is_own_message", False))
    if not mentioned:
        return {"action": "skip", "reason": "ringkas-ambient-observed"}
    return None


def register(ctx):
    ctx.register_hook("pre_gateway_dispatch", _simpan_pesan_masuk)
