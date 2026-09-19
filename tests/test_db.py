import sqlite3

import pytest

from ringkas.db import (
    ambil_pengaturan_grup,
    ambil_pesan,
    cari_pesan,
    get_or_create_group,
    get_or_create_member,
    init_db,
    insert_message,
    simpan_ringkasan,
    tambah_item,
)


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    init_db(connection)
    yield connection
    connection.close()


def test_init_db_membuat_semua_tabel(conn):
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    expected = {
        "groups",
        "members",
        "messages",
        "summaries",
        "items",
        "reminders",
        "magic_links",
        "stats_daily",
    }
    assert expected.issubset(tables)


def test_get_or_create_group_idempoten(conn):
    gid1 = get_or_create_group(conn, "-100123", nama="Grup Uji")
    gid2 = get_or_create_group(conn, "-100123", nama="Grup Uji")
    assert gid1 == gid2


def test_get_or_create_member_idempoten(conn):
    mid1 = get_or_create_member(conn, "861697558", nama_tampilan="Muhammad")
    mid2 = get_or_create_member(conn, "861697558", nama_tampilan="Muhammad")
    assert mid1 == mid2


def test_insert_message_dan_fts_search(conn):
    gid = get_or_create_group(conn, "-100123")
    mid = get_or_create_member(conn, "861697558", "Muhammad")
    insert_message(
        conn,
        group_id=gid,
        telegram_msg_id="1",
        sender_id=mid,
        teks="iuran study tour paling lambat Jumat",
        jenis="text",
        is_noise=False,
    )
    insert_message(
        conn,
        group_id=gid,
        telegram_msg_id="2",
        sender_id=mid,
        teks="ok",
        jenis="text",
        is_noise=True,
    )

    rows = conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()
    assert rows["c"] == 2

    hasil = conn.execute(
        "SELECT m.teks FROM messages_fts f JOIN messages m ON m.id = f.rowid WHERE messages_fts MATCH 'iuran'"
    ).fetchall()
    assert len(hasil) == 1
    assert "iuran" in hasil[0]["teks"]


def test_insert_message_idempoten_untuk_msg_id_sama(conn):
    gid = get_or_create_group(conn, "-100123")
    id1 = insert_message(conn, group_id=gid, telegram_msg_id="1", sender_id=None, teks="halo")
    id2 = insert_message(conn, group_id=gid, telegram_msg_id="1", sender_id=None, teks="halo lagi")
    assert id1 == id2
    count = conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()["c"]
    assert count == 1


def test_ambil_pesan_filter_periode_dan_noise(conn):
    gid = get_or_create_group(conn, "-100123")
    insert_message(conn, group_id=gid, telegram_msg_id="1", sender_id=None, teks="penting",
                    is_noise=False, jenis="text")
    insert_message(conn, group_id=gid, telegram_msg_id="2", sender_id=None, teks="ok",
                    is_noise=True, jenis="text")

    hasil = ambil_pesan(conn, group_id=gid, sejak="2000-01-01T00:00:00+00:00", sampai="2100-01-01T00:00:00+00:00")
    assert len(hasil) == 1
    assert hasil[0]["teks"] == "penting"

    hasil_semua = ambil_pesan(
        conn, group_id=gid, sejak="2000-01-01T00:00:00+00:00", sampai="2100-01-01T00:00:00+00:00", tanpa_noise=False
    )
    assert len(hasil_semua) == 2


def test_cari_pesan_fts(conn):
    gid = get_or_create_group(conn, "-100123")
    insert_message(conn, group_id=gid, telegram_msg_id="1", sender_id=None, teks="iuran study tour 250rb")
    insert_message(conn, group_id=gid, telegram_msg_id="2", sender_id=None, teks="cuaca hari ini cerah")

    hasil = cari_pesan(conn, group_id=gid, query="iuran")
    assert len(hasil) == 1
    assert "iuran" in hasil[0]["teks"]


def test_simpan_ringkasan_dan_tambah_item(conn):
    gid = get_or_create_group(conn, "-100123")
    msg_id = insert_message(conn, group_id=gid, telegram_msg_id="1", sender_id=None, teks="iuran 50rb Jumat")

    summary_id = simpan_ringkasan(
        conn,
        group_id=gid,
        periode_mulai="2026-09-19T00:00:00+00:00",
        periode_selesai="2026-09-19T23:59:59+00:00",
        isi_markdown="ringkasan test",
        jumlah_pesan=1,
        jumlah_penting=1,
    )
    assert summary_id > 0

    item_id = tambah_item(
        conn,
        group_id=gid,
        summary_id=summary_id,
        tipe="tenggat",
        judul="Iuran",
        detail="50rb",
        due_at="2026-09-25T00:00:00+00:00",
        source_msg_ids=[msg_id],
    )
    assert item_id > 0

    row = conn.execute("SELECT source_msg_ids FROM items WHERE id = ?", (item_id,)).fetchone()
    assert row["source_msg_ids"] == f"[{msg_id}]"


def test_ambil_pengaturan_grup(conn):
    gid = get_or_create_group(conn, "-100123", nama="Grup Uji")
    pengaturan = ambil_pengaturan_grup(conn, group_id=gid)
    assert pengaturan["nama"] == "Grup Uji"
    assert pengaturan["retensi_hari"] == 7
    assert pengaturan["kata_kunci_penting"] == []
