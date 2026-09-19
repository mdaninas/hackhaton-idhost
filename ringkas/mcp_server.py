"""MCP server untuk Ringkas. Tool untuk H2: simpan_pesan saja.

Tool lain (ambil_pesan, cari_pesan, simpan_ringkasan, dst) menyusul di H3.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from ringkas.db import connect, get_or_create_group, get_or_create_member, insert_message
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
    noise = is_noise(teks, jenis=jenis)
    with connect() as conn:
        group_id = get_or_create_group(conn, chat_id)
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


if __name__ == "__main__":
    mcp.run()
