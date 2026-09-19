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
```

(`0 13 * * *` = jam 20:00 WIB, karena VPS ini pakai UTC.)
