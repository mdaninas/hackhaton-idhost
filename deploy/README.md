# Deploy — setup Hermes cron & plugin

Langkah manual yang perlu dijalankan sekali di VPS setelah clone repo (belum
diotomatisasi, dicatat di sini supaya reproducible):

## Plugin Hermes

```bash
mkdir -p ~/.hermes/plugins
ln -s "$(pwd)/hermes/plugins/ringkas" ~/.hermes/plugins/ringkas
hermes plugins enable ringkas
```

## MCP server

```bash
hermes mcp add ringkas --command "$(pwd)/.venv/bin/python" \
  --env RINGKAS_DB_PATH="$(pwd)/data/ringkas.db" PYTHONPATH="$(pwd)" \
  --args "$(pwd)/ringkas/mcp_server.py"
```

## Cron scripts

Symlink DITOLAK Hermes untuk script cron (guard keamanan menolak path yang
resolve keluar dari `~/.hermes/scripts/`). Copy manual file wrapper di folder
ini ke `~/.hermes/scripts/`:

```bash
cp deploy/hermes-scripts/*.py ~/.hermes/scripts/
```

Lalu daftarkan job-nya:

```bash
hermes cron create "every 5m" --no-agent --script ringkas_send_reminders.py \
  --deliver local --name "ringkas-reminder-check"

hermes cron create "0 13 * * *" --no-agent --script ringkas_daily_summary.py \
  --deliver local --name "ringkas-daily-summary"

hermes cron create "5 13 * * *" --no-agent --script ringkas_dm_summary.py \
  --deliver local --name "ringkas-dm-summary"

hermes cron create "30 13 * * *" --no-agent --script ringkas_retensi.py \
  --deliver local --name "ringkas-retensi"
```

(`0 13 * * *` = jam 20:00 WIB, `5 13 * * *` = 20:05 WIB, `30 13 * * *` = 20:30
WIB, karena VPS ini pakai UTC.)

## Gateway sebagai systemd service (H7)

```bash
sudo hermes gateway install --system --run-as-user root --start-now --start-on-login
```

`--run-as-user root` WAJIB di VPS ini karena seluruh setup (plugin, DB, .env)
ada di bawah `/root` -- Hermes menolak install sebagai root secara default
tanpa flag ini. Restart setelah update kode: `systemctl restart hermes-gateway`.

## Allowlist Telegram (H6/H7)

- **Grup & chat**: `TELEGRAM_GROUP_ALLOWED_CHATS` / `TELEGRAM_ALLOWED_CHATS`
  HARUS DIKOSONGKAN (bukan diisi `"*"` -- itu tidak didukung untuk chat/grup
  di versi Hermes ini, cuma untuk user) supaya bot bisa dipakai di grup
  manapun. Kalau perlu dibatasi ke grup tertentu, isi dengan chat_id
  dipisah koma.
- **DM personal** (`/mulai`, `/konteks`): `TELEGRAM_ALLOWED_USERS=*` supaya
  siapa saja bisa pakai fitur DM. Bisa dibatasi ke user tertentu (pisah koma)
  kalau mau kontrol biaya OpenAI API lebih ketat.
