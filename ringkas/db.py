"""Skema SQLite dan helper akses database untuk Ringkas.

Semua waktu disimpan dalam UTC (ISO 8601, kolom TEXT). Konversi ke WIB
dilakukan di lapisan presentasi (bot/dashboard), bukan di sini.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ringkas.db"


def now_utc_iso() -> str:
    """Waktu sekarang dalam UTC, format ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def get_db_path() -> Path:
    """Path database, dari env var RINGKAS_DB_PATH atau default data/ringkas.db."""
    env_path = os.environ.get("RINGKAS_DB_PATH")
    return Path(env_path) if env_path else DEFAULT_DB_PATH


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Buka koneksi SQLite dengan mode WAL dan foreign keys aktif."""
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)  # idempoten (CREATE TABLE IF NOT EXISTS) -- pastikan skema selalu ada
    return conn


@contextmanager
def connect(db_path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    """Context manager: buka koneksi, commit di akhir, tutup selalu."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_chat_id TEXT NOT NULL UNIQUE,
    nama TEXT,
    jam_ringkasan TEXT NOT NULL DEFAULT '20:00',
    kata_kunci_penting TEXT NOT NULL DEFAULT '[]',
    retensi_hari INTEGER NOT NULL DEFAULT 7,
    aktif INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id TEXT NOT NULL UNIQUE,
    nama_tampilan TEXT,
    dm_aktif INTEGER NOT NULL DEFAULT 0,
    konteks_personal TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL REFERENCES groups(id),
    telegram_msg_id TEXT NOT NULL,
    sender_id INTEGER REFERENCES members(id),
    teks TEXT NOT NULL DEFAULT '',
    jenis TEXT NOT NULL DEFAULT 'text',
    is_noise INTEGER NOT NULL DEFAULT 0,
    reply_to TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (group_id, telegram_msg_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_group_created
    ON messages (group_id, created_at);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5 (
    teks,
    content='messages',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts (rowid, teks) VALUES (new.id, new.teks);
END;

CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts (messages_fts, rowid, teks) VALUES ('delete', old.id, old.teks);
END;

CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts (messages_fts, rowid, teks) VALUES ('delete', old.id, old.teks);
    INSERT INTO messages_fts (rowid, teks) VALUES (new.id, new.teks);
END;

CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL REFERENCES groups(id),
    periode_mulai TEXT NOT NULL,
    periode_selesai TEXT NOT NULL,
    isi_markdown TEXT NOT NULL,
    jumlah_pesan INTEGER NOT NULL DEFAULT 0,
    jumlah_penting INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL REFERENCES groups(id),
    summary_id INTEGER REFERENCES summaries(id),
    tipe TEXT NOT NULL,
    judul TEXT NOT NULL,
    detail TEXT,
    due_at TEXT,
    source_msg_ids TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'aktif'
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES items(id),
    kirim_pada TEXT NOT NULL,
    target TEXT NOT NULL,
    terkirim INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS magic_links (
    token TEXT PRIMARY KEY,
    telegram_user_id TEXT NOT NULL,
    group_id INTEGER NOT NULL REFERENCES groups(id),
    expires_at TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stats_daily (
    group_id INTEGER NOT NULL REFERENCES groups(id),
    tanggal TEXT NOT NULL,
    pesan_masuk INTEGER NOT NULL DEFAULT 0,
    pesan_noise INTEGER NOT NULL DEFAULT 0,
    item_penting INTEGER NOT NULL DEFAULT 0,
    tenggat_terdeteksi INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (group_id, tanggal)
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    """Buat semua tabel (dan FTS5) kalau belum ada. Idempoten."""
    conn.executescript(SCHEMA)


def get_or_create_group(conn: sqlite3.Connection, telegram_chat_id: str, nama: Optional[str] = None) -> int:
    """Cari group by telegram_chat_id, buat baru kalau belum ada. Return group_id."""
    row = conn.execute(
        "SELECT id FROM groups WHERE telegram_chat_id = ?", (telegram_chat_id,)
    ).fetchone()
    if row is not None:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO groups (telegram_chat_id, nama, created_at) VALUES (?, ?, ?)",
        (telegram_chat_id, nama, now_utc_iso()),
    )
    return cur.lastrowid


def get_or_create_member(
    conn: sqlite3.Connection, telegram_user_id: str, nama_tampilan: Optional[str] = None
) -> int:
    """Cari member by telegram_user_id, buat baru kalau belum ada. Return member_id."""
    row = conn.execute(
        "SELECT id, nama_tampilan FROM members WHERE telegram_user_id = ?", (telegram_user_id,)
    ).fetchone()
    if row is not None:
        if nama_tampilan and row["nama_tampilan"] != nama_tampilan:
            conn.execute(
                "UPDATE members SET nama_tampilan = ? WHERE id = ?",
                (nama_tampilan, row["id"]),
            )
        return row["id"]
    cur = conn.execute(
        "INSERT INTO members (telegram_user_id, nama_tampilan) VALUES (?, ?)",
        (telegram_user_id, nama_tampilan),
    )
    return cur.lastrowid


def insert_message(
    conn: sqlite3.Connection,
    *,
    group_id: int,
    telegram_msg_id: str,
    sender_id: Optional[int],
    teks: str,
    jenis: str = "text",
    is_noise: bool = False,
    reply_to: Optional[str] = None,
) -> int:
    """Simpan satu pesan. Aman dipanggil ulang untuk (group_id, telegram_msg_id) yang sama (idempoten)."""
    row = conn.execute(
        "SELECT id FROM messages WHERE group_id = ? AND telegram_msg_id = ?",
        (group_id, telegram_msg_id),
    ).fetchone()
    if row is not None:
        return row["id"]
    cur = conn.execute(
        """
        INSERT INTO messages (group_id, telegram_msg_id, sender_id, teks, jenis, is_noise, reply_to, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (group_id, telegram_msg_id, sender_id, teks, jenis, int(is_noise), reply_to, now_utc_iso()),
    )
    return cur.lastrowid


def ambil_pesan(
    conn: sqlite3.Connection,
    *,
    group_id: int,
    sejak: str,
    sampai: str,
    tanpa_noise: bool = True,
    limit: int = 1000,
) -> list[sqlite3.Row]:
    """Ambil pesan grup dalam rentang waktu [sejak, sampai) (UTC ISO), urut waktu."""
    query = """
        SELECT m.id, m.teks, m.jenis, m.is_noise, m.created_at, m.reply_to,
               COALESCE(mem.nama_tampilan, mem.telegram_user_id) AS sender_nama
        FROM messages m
        LEFT JOIN members mem ON mem.id = m.sender_id
        WHERE m.group_id = ? AND m.created_at >= ? AND m.created_at < ?
    """
    params: list = [group_id, sejak, sampai]
    if tanpa_noise:
        query += " AND m.is_noise = 0"
    query += " ORDER BY m.created_at ASC LIMIT ?"
    params.append(limit)
    return conn.execute(query, params).fetchall()


def cari_pesan(conn: sqlite3.Connection, *, group_id: int, query: str, limit: int = 20) -> list[sqlite3.Row]:
    """Cari pesan grup lewat FTS5. `query` mengikuti sintaks MATCH FTS5."""
    return conn.execute(
        """
        SELECT m.id, m.teks, m.created_at, COALESCE(mem.nama_tampilan, mem.telegram_user_id) AS sender_nama
        FROM messages_fts f
        JOIN messages m ON m.id = f.rowid
        LEFT JOIN members mem ON mem.id = m.sender_id
        WHERE messages_fts MATCH ? AND m.group_id = ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, group_id, limit),
    ).fetchall()


def simpan_ringkasan(
    conn: sqlite3.Connection,
    *,
    group_id: int,
    periode_mulai: str,
    periode_selesai: str,
    isi_markdown: str,
    jumlah_pesan: int,
    jumlah_penting: int,
) -> int:
    """Simpan satu ringkasan. Return summary_id."""
    cur = conn.execute(
        """
        INSERT INTO summaries (group_id, periode_mulai, periode_selesai, isi_markdown, jumlah_pesan, jumlah_penting, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (group_id, periode_mulai, periode_selesai, isi_markdown, jumlah_pesan, jumlah_penting, now_utc_iso()),
    )
    return cur.lastrowid


def tambah_item(
    conn: sqlite3.Connection,
    *,
    group_id: int,
    summary_id: Optional[int],
    tipe: str,
    judul: str,
    detail: Optional[str],
    due_at: Optional[str],
    source_msg_ids: list[int],
) -> int:
    """Simpan satu item (pengumuman/tenggat/keputusan/pertanyaan). Return item_id."""
    cur = conn.execute(
        """
        INSERT INTO items (group_id, summary_id, tipe, judul, detail, due_at, source_msg_ids, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'aktif')
        """,
        (group_id, summary_id, tipe, judul, detail, due_at, json.dumps(source_msg_ids)),
    )
    return cur.lastrowid


def ambil_pengaturan_grup(conn: sqlite3.Connection, *, group_id: int) -> dict:
    """Ambil pengaturan grup (jam_ringkasan, kata_kunci_penting, retensi_hari, dst)."""
    row = conn.execute(
        "SELECT telegram_chat_id, nama, jam_ringkasan, kata_kunci_penting, retensi_hari, aktif FROM groups WHERE id = ?",
        (group_id,),
    ).fetchone()
    if row is None:
        return {}
    return {
        "telegram_chat_id": row["telegram_chat_id"],
        "nama": row["nama"],
        "jam_ringkasan": row["jam_ringkasan"],
        "kata_kunci_penting": json.loads(row["kata_kunci_penting"]),
        "retensi_hari": row["retensi_hari"],
        "aktif": bool(row["aktif"]),
    }
