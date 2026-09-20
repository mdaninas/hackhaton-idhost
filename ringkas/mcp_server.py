"""MCP server untuk Ringkas.

Tool untuk dipanggil agent Hermes secara langsung (Q&A, ringkasan ad-hoc
saat di-mention, dst). Perintah `/ringkas` sendiri TIDAK lewat sini -- dia
langsung panggil fungsi ringkas/db.py dari dalam plugin demi kesederhanaan
(lihat hermes/plugins/ringkas/__init__.py).
"""

from __future__ import annotations

from typing import Optional

from mcp.server.mcpserver import MCPServer

from ringkas.db import (
    ambil_pengaturan_grup as _ambil_pengaturan_grup,
    ambil_pesan as _ambil_pesan,
    cari_pesan as _cari_pesan,
    connect,
    daftar_tenggat as _daftar_tenggat,
    get_or_create_group,
    get_or_create_member,
    insert_message,
    pesan_ids_valid,
    simpan_ringkasan as _simpan_ringkasan,
    simpan_tenggat_dengan_pengingat,
    tambah_item,
    tambah_kata_kunci_penting,
)
from ringkas.noise_filter import is_noise

mcp = MCPServer("ringkas")


@mcp.tool()
def simpan_pesan(
    chat_id: str,
    telegram_msg_id: str,
    teks: str,
    sender_id: str,
    sender_nama: str = "",
    jenis: str = "text",
    reply_to: str = "",
) -> dict:
    """Simpan satu pesan grup Telegram ke database, tandai noise otomatis.

    Args:
        chat_id: Telegram chat ID grup (string, boleh negatif, mis. "-5303407935").
        telegram_msg_id: ID unik pesan dari Telegram, dipakai supaya tidak dobel simpan.
        teks: Isi teks pesan (kosongkan untuk stiker/foto tanpa caption).
        sender_id: Telegram user ID pengirim.
        sender_nama: Nama tampilan pengirim (opsional).
        jenis: "text" | "sticker" | "photo" | "gif" | dst.
        reply_to: telegram_msg_id pesan yang di-reply, kalau ada.

    Returns:
        dict berisi message_id (di database) dan is_noise.
    """
    with connect() as conn:
        group_id = get_or_create_group(conn, chat_id)
        kata_kunci = _ambil_pengaturan_grup(conn, group_id=group_id).get("kata_kunci_penting", [])
        noise = is_noise(teks, jenis=jenis, kata_kunci_penting=kata_kunci)
        member_id = get_or_create_member(conn, sender_id, sender_nama or None)
        message_id = insert_message(
            conn,
            group_id=group_id,
            telegram_msg_id=telegram_msg_id,
            sender_id=member_id,
            teks=teks,
            jenis=jenis,
            is_noise=noise,
            reply_to=reply_to or None,
        )
    return {"message_id": message_id, "is_noise": noise}


@mcp.tool()
def ambil_pesan(chat_id: str, sejak: str, sampai: str, tanpa_noise: bool = True, limit: int = 500) -> list[dict]:
    """Ambil pesan grup dalam rentang waktu untuk diringkas.

    Args:
        chat_id: Telegram chat ID grup.
        sejak: Waktu mulai, format ISO 8601 UTC (mis. "2026-09-19T00:00:00+00:00").
        sampai: Waktu akhir, format ISO 8601 UTC.
        tanpa_noise: Kalau True, pesan noise (stiker, "ok", dst) tidak disertakan.
        limit: Jumlah maksimum pesan.

    Returns:
        List pesan {id, teks, jenis, sender_nama, created_at}, urut waktu.
        `id` di sini WAJIB dipakai sebagai isi source_msg_ids kalau item ini
        dipakai untuk simpan_ringkasan -- jangan mengarang id yang tidak ada di sini.
    """
    with connect() as conn:
        group_id = get_or_create_group(conn, chat_id)
        rows = _ambil_pesan(conn, group_id=group_id, sejak=sejak, sampai=sampai, tanpa_noise=tanpa_noise, limit=limit)
    return [
        {"id": r["id"], "teks": r["teks"], "jenis": r["jenis"], "sender_nama": r["sender_nama"], "created_at": r["created_at"]}
        for r in rows
    ]


@mcp.tool()
def cari_pesan(chat_id: str, query: str, limit: int = 20) -> list[dict]:
    """Cari pesan lama di grup (untuk menjawab pertanyaan riwayat grup).

    Args:
        chat_id: Telegram chat ID grup.
        query: Kata kunci pencarian (sintaks FTS5 SQLite, kata biasa juga jalan).
        limit: Jumlah maksimum hasil.

    Returns:
        List pesan {id, teks, sender_nama, created_at} yang cocok, paling relevan duluan.
    """
    with connect() as conn:
        group_id = get_or_create_group(conn, chat_id)
        rows = _cari_pesan(conn, group_id=group_id, query=query, limit=limit)
    return [{"id": r["id"], "teks": r["teks"], "sender_nama": r["sender_nama"], "created_at": r["created_at"]} for r in rows]


@mcp.tool()
def simpan_ringkasan(
    chat_id: str,
    periode_mulai: str,
    periode_selesai: str,
    isi_markdown: str,
    jumlah_pesan: int,
    jumlah_penting: int,
    items: Optional[list[dict]] = None,
) -> dict:
    """Simpan hasil ringkasan + item-item pentingnya.

    Args:
        chat_id: Telegram chat ID grup.
        periode_mulai: Awal periode ringkasan, ISO 8601 UTC.
        periode_selesai: Akhir periode ringkasan, ISO 8601 UTC.
        isi_markdown: Teks ringkasan lengkap (format sesuai skill ringkas).
        jumlah_pesan: Total pesan pada periode ini.
        jumlah_penting: Jumlah pesan yang dianggap penting (bukan noise).
        items: List item, masing-masing dict dengan keys:
            tipe ("pengumuman"|"tenggat"|"keputusan"|"pertanyaan"), judul, detail,
            source_msg_ids (list int, WAJIB berasal dari id hasil ambil_pesan/cari_pesan
            -- id yang tidak valid otomatis dibuang, item tanpa id valid dibuang seluruhnya).
            Untuk tipe "tenggat", isi juga due_date_wib ("YYYY-MM-DD", tanggal WIB PASTI,
            bukan "Kamis depan" mentah -- hitung dari tanggal hari ini) dan due_time_wib
            (opsional, "HH:MM"). Kalau tanggal pasti tidak bisa ditentukan, jangan pakai
            tipe "tenggat" -- pakai "pengumuman" saja.

    Returns:
        dict berisi summary_id dan jumlah item tersimpan.
    """
    with connect() as conn:
        group_id = get_or_create_group(conn, chat_id)
        summary_id = _simpan_ringkasan(
            conn,
            group_id=group_id,
            periode_mulai=periode_mulai,
            periode_selesai=periode_selesai,
            isi_markdown=isi_markdown,
            jumlah_pesan=jumlah_pesan,
            jumlah_penting=jumlah_penting,
        )
        for item in items or []:
            judul = item.get("judul", "")
            source_msg_ids = item.get("source_msg_ids", [])
            if not judul or not pesan_ids_valid(conn, group_id=group_id, ids=source_msg_ids):
                continue
            if item.get("tipe") == "tenggat" and item.get("due_date_wib"):
                simpan_tenggat_dengan_pengingat(
                    conn,
                    group_id=group_id,
                    summary_id=summary_id,
                    judul=judul,
                    detail=item.get("detail"),
                    due_date_wib=item["due_date_wib"],
                    due_time_wib=item.get("due_time_wib", ""),
                    source_msg_ids=source_msg_ids,
                )
            else:
                ids_valid = list(pesan_ids_valid(conn, group_id=group_id, ids=source_msg_ids))
                tambah_item(
                    conn,
                    group_id=group_id,
                    summary_id=summary_id,
                    tipe=item.get("tipe", "pengumuman"),
                    judul=judul,
                    detail=item.get("detail"),
                    due_at=None,
                    source_msg_ids=ids_valid,
                )
    return {"summary_id": summary_id, "items_disimpan": len(items or [])}


@mcp.tool()
def tambah_tenggat(
    chat_id: str,
    judul: str,
    due_date_wib: str,
    source_msg_ids: list[int],
    due_time_wib: str = "",
    detail: str = "",
) -> dict:
    """Buat satu item tenggat + jadwalkan pengingat otomatis (H-1 dan hari-H pagi, WIB).

    Args:
        chat_id: Telegram chat ID grup.
        judul: Judul singkat tenggat (mis. "Bayar iuran study tour").
        due_date_wib: Tanggal deadline PASTI, format "YYYY-MM-DD", zona WIB.
            Hitung dari tanggal hari ini + ekspresi waktu di pesan (mis. "Kamis" -> tanggal
            Kamis terdekat ke depan). Kalau tidak bisa dipastikan, JANGAN panggil tool ini.
        source_msg_ids: id pesan (dari ambil_pesan/cari_pesan) yang jadi dasar tenggat ini.
        due_time_wib: Jam deadline kalau disebutkan di pesan, format "HH:MM" (opsional).
        detail: Detail tambahan (opsional).

    Returns:
        dict berisi item_id, jumlah pengingat terjadwal, dan due_label untuk ditampilkan.
    """
    with connect() as conn:
        group_id = get_or_create_group(conn, chat_id)
        hasil = simpan_tenggat_dengan_pengingat(
            conn,
            group_id=group_id,
            summary_id=None,
            judul=judul,
            detail=detail or None,
            due_date_wib=due_date_wib,
            due_time_wib=due_time_wib,
            source_msg_ids=source_msg_ids,
        )
    return {
        "item_id": hasil["item_id"],
        "pengingat_terjadwal": len(hasil["reminder_ids"]),
        "due_label": hasil["due_label"],
        "source_msg_ids_valid": hasil["source_msg_ids"],
    }


@mcp.tool()
def daftar_tenggat(chat_id: str) -> list[dict]:
    """Daftar tenggat aktif (belum ditandai selesai) untuk sebuah grup, urut tanggal terdekat.

    Args:
        chat_id: Telegram chat ID grup.
    """
    with connect() as conn:
        group_id = get_or_create_group(conn, chat_id)
        rows = _daftar_tenggat(conn, group_id=group_id)
    return [
        {"id": r["id"], "judul": r["judul"], "detail": r["detail"], "due_at": r["due_at"]}
        for r in rows
    ]


@mcp.tool()
def ambil_pengaturan_grup(chat_id: str) -> dict:
    """Ambil pengaturan grup: jam ringkasan, kata kunci penting, retensi data, dst.

    Args:
        chat_id: Telegram chat ID grup.
    """
    with connect() as conn:
        group_id = get_or_create_group(conn, chat_id)
        return _ambil_pengaturan_grup(conn, group_id=group_id)


@mcp.tool()
def koreksi_penting(chat_id: str, kata_kunci: str) -> dict:
    """Catat koreksi: pesan yang menyinggung kata kunci ini SELALU dianggap penting.

    Panggil tool ini kalau seorang anggota grup secara eksplisit bilang sesuatu
    itu penting dan minta diingat (mis. "itu penting, inget ya", "jangan
    dianggap noise ya kalau soal X"). Efeknya berlaku untuk pesan BERIKUTNYA
    (bukan ringkasan yang sudah dibuat sebelumnya).

    Args:
        chat_id: Telegram chat ID grup.
        kata_kunci: Kata/frasa yang harus selalu dianggap penting (mis. "iuran", "study tour").

    Returns:
        dict berisi daftar kata_kunci_penting grup ini setelah update.
    """
    with connect() as conn:
        group_id = get_or_create_group(conn, chat_id)
        daftar = tambah_kata_kunci_penting(conn, group_id=group_id, kata_kunci=kata_kunci)
    return {"kata_kunci_penting": daftar}


if __name__ == "__main__":
    mcp.run()
