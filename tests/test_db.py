import sqlite3

import pytest

from ringkas.db import get_or_create_group, get_or_create_member, init_db, insert_message


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
