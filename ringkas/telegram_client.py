"""Helper kecil kirim pesan Telegram tanpa dependency tambahan (stdlib saja).

Dipakai script cron no_agent (send_reminders.py, daily_summary.py) yang
env-nya disanitasi Hermes -- baca token langsung dari file .env, bukan
os.environ.
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

ENV_PATH = Path.home() / ".hermes" / ".env"


def baca_bot_token() -> str:
    text = ENV_PATH.read_text()
    m = re.search(r"^TELEGRAM_BOT_TOKEN=(.+)$", text, re.MULTILINE)
    if not m:
        raise RuntimeError("TELEGRAM_BOT_TOKEN tidak ditemukan di .env")
    return m.group(1).strip()


def baca_openai_key() -> str:
    text = ENV_PATH.read_text()
    m = re.search(r"^OPENAI_API_KEY=(.+)$", text, re.MULTILINE)
    if not m:
        raise RuntimeError("OPENAI_API_KEY tidak ditemukan di .env")
    return m.group(1).strip()


def kirim_pesan(token: str, chat_id: str, teks: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": teks}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()
