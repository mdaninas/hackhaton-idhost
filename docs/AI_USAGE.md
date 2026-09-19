# AI_USAGE — Catatan Penggunaan AI

> Dicatat sambil jalan untuk transparansi di artikel lomba. Setiap entri: hari, apa yang dikerjakan Claude Code, dan sejauh mana (dibuat penuh / dibantu / direview).

## H1 — 2026-09-18/19: Fondasi & keputusan arsitektur

- **Setup VPS & Hermes:** Claude Code mendiagnosis dan memperbaiki beberapa masalah konfigurasi Hermes Agent bawaan VPS (routing LLM yang salah, model/provider tidak cocok, gateway Telegram hang karena isu IPv6) — dibuat penuh oleh Claude Code, diverifikasi lewat smoke test dan log real-time.
- **Riset dokumentasi:** Claude Code membaca source code Hermes Agent yang terinstal lokal (bukan cuma dokumentasi web) untuk memverifikasi perilaku provider LLM dan gateway Telegram, setelah mendeteksi konten mencurigakan (kemungkinan prompt injection) di hasil fetch dokumentasi web resmi.
- **Konfigurasi gateway Telegram:** Claude Code menemukan dan menerapkan kombinasi env var yang tepat (`TELEGRAM_GROUP_ALLOWED_CHATS`, `TELEGRAM_REQUIRE_MENTION`, `TELEGRAM_OBSERVE_UNMENTIONED_GROUP_MESSAGES`) agar bot bisa membaca semua pesan grup tapi hanya membalas saat di-mention — dibuat penuh oleh Claude Code, diverifikasi langsung oleh Dani di Telegram.
- **Nama bot:** Claude Code mengusulkan beberapa opsi nama bot Telegram; Dani memilih dan mendaftarkan `ringkasgrup_bot` di @BotFather sendiri.
- **Dokumentasi keputusan:** `docs/DECISIONS.md` (Plan A vs Plan B, konfigurasi final, catatan bug environment) ditulis oleh Claude Code berdasarkan hasil spike test bersama Dani.

## H2 — 2026-09-19: Database & penerimaan pesan

- **`ringkas/db.py`** (skema SQLite lengkap + FTS5 + trigger sync) — dibuat penuh oleh Claude Code sesuai model data di `PLAN.md` bagian 5.
- **`ringkas/noise_filter.py`** (penyaring noise berbasis aturan) — dibuat penuh oleh Claude Code sesuai aturan di `PLAN.md` bagian 7, termasuk daftar kata singkat dan pola tanggal/nominal uang.
- **16 unit test** (`tests/test_db.py`, `tests/test_noise_filter.py`) — ditulis penuh oleh Claude Code, mencakup idempotensi, pencarian FTS5, dan berbagai kasus noise/bukan-noise.
- **Investigasi arsitektur:** Claude Code menemukan bahwa fitur observe-mode bawaan Hermes tidak bisa diintersep plugin untuk penyimpanan pesan (dikonfirmasi lewat pembacaan source code Hermes langsung), lalu merancang dan mengimplementasikan solusi alternatif berupa plugin Hermes kustom (`hermes/plugins/ringkas/`) yang mengambil alih logika "simpan semua pesan + diam kecuali di-mention" lewat hook `pre_gateway_dispatch`. Sepenuhnya dirancang dan diimplementasikan oleh Claude Code, diverifikasi langsung di grup Telegram bersama Dani.
- **MCP server** (`ringkas/mcp_server.py`, tool `simpan_pesan`) — dibuat oleh Claude Code, terdaftar ke Hermes lewat `hermes mcp add`.

## H3 — 2026-09-19: MCP server lengkap & perintah /ringkas

- **4 MCP tool tambahan** (`ambil_pesan`, `cari_pesan`, `simpan_ringkasan`, `ambil_pengaturan_grup`) di `ringkas/mcp_server.py` dan fungsi pendukungnya di `ringkas/db.py` — dibuat penuh oleh Claude Code sesuai kontrak di `PLAN.md` bagian 6, plus 5 unit test tambahan.
- **Perintah `/ringkas`** (`hermes/plugins/ringkas/__init__.py`) — dirancang dan diimplementasikan penuh oleh Claude Code memakai `ctx.llm.complete_structured()` (panggilan LLM one-shot dari plugin, bukan lewat turn agent biasa) setelah riset dokumentasi Hermes menunjukkan slash command plugin tidak punya akses ke sesi percakapan. Termasuk logika anti-mengarang (validasi `source_msg_ids` terhadap pesan yang benar-benar ada) yang sepenuhnya dirancang Claude Code.
- Diverifikasi langsung di grup Telegram bersama Dani: 6 pesan campuran terkirim, `/ringkas` menghasilkan ringkasan sesuai format `PLAN.md`, semua item bersumber dari pesan asli, pesan noise ter-filter dengan benar.

## H4 — 2026-09-19: Tenggat, pengingat, dan ringkasan harian otomatis

- **Ekstraksi tanggal tenggat pasti** (skema `due_date_wib`/`due_time_wib` + konteks tanggal hari ini di prompt LLM) dan **penjadwalan pengingat H-1/hari-H** (`ringkas.db.simpan_tenggat_dengan_pengingat`) — dirancang dan diimplementasikan penuh oleh Claude Code.
- **`ringkas/daily_summary.py`** (ringkasan otomatis harian) dan **`ringkas/send_reminders.py`** (pengirim pengingat) — dibuat penuh oleh Claude Code sebagai cron job `no_agent`, setelah riset dokumentasi Hermes yang menunjukkan agent tidak otomatis tahu tanggal saat ini (perlu tool `terminal`), sehingga pendekatan yang lebih deterministik (panggil OpenAI API langsung, bukan lewat sesi agent) dipilih.
- Debugging mandiri oleh Claude Code: error `temperature` tidak didukung model `gpt-5-mini` di endpoint chat completions, dan pembatasan keamanan Hermes yang menolak symlink script cron (diselesaikan dengan wrapper script fisik).
- Kedua cron job diverifikasi live bersama Dani: pengingat terkirim tepat waktu (uji manual + lewat scheduler asli Hermes), ringkasan harian terkirim ke grup Telegram end-to-end.
