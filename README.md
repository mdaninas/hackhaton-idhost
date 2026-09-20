# Ringkas — Asisten Ringkasan Grup Chat

Bot Telegram berbasis [Hermes Agent](https://hermes-agent.nousresearch.com) yang membaca grup chat, menyaring noise, mengirim ringkasan harian, mendeteksi tenggat + pengingat otomatis, menjawab pertanyaan riwayat grup, dan mengirim ringkasan personal lewat DM.

Dibuat untuk **IDwebhost AI Hackfest 2026**, kategori Productivity & Personal AI.

## Fitur

- **Penyaring noise** berbasis aturan (stiker kosong, "ok"/"siap"/dst, emoji saja, ucapan tanpa info) sebelum pesan masuk LLM
- **Ringkasan harian otomatis** (default jam 20:00 WIB) + ringkasan manual (`/ringkas`)
- **Deteksi tenggat** dengan tanggal pasti (WIB) + pengingat otomatis H-1 dan hari-H
- **Tanya jawab riwayat grup** — mention bot, dijawab dengan sumber, jujur kalau tidak tahu
- **Ringkasan personal DM** (`/mulai`, `/konteks <cerita>`) yang menyorot info relevan per orang
- **Memori koreksi** — bilang "itu penting, inget ya" ke bot, mempengaruhi ringkasan berikutnya
- **Kontrol privasi** — pesan perkenalan transparan, retensi data otomatis (default 7 hari), `/hapusdata` (admin-only)
- **`/statistik`** — pesan masuk, noise, item penting, tenggat aktif, estimasi waktu hemat

## Arsitektur

Hermes Agent memegang koneksi Telegram sepenuhnya (Plan A). Plugin kustom (`hermes/plugins/ringkas/`) mengambil alih logika "simpan semua pesan + diam kecuali di-mention" lewat hook `pre_gateway_dispatch`, karena fitur observe-mode bawaan Hermes ternyata tidak bisa diintersep untuk keperluan penyimpanan (lihat `docs/DECISIONS.md`).

Ringkasan harian & pengingat berjalan sebagai cron job `no_agent` (tanpa sesi LLM Hermes) yang memanggil OpenAI langsung — karena agent Hermes tidak otomatis tahu tanggal/jam saat ini, tidak cocok untuk job berjadwal tetap.

```
Grup Telegram ──► Hermes Gateway (plugin ringkas) ──► SQLite (WAL + FTS5)
                        │                                    ▲
                        ▼                                    │
                  MCP tools (ambil_pesan, cari_pesan,   Cron jobs (no_agent):
                  simpan_ringkasan, tambah_tenggat, dst)  - ringkasan harian
                        │                                 - pengingat tenggat
                        ▼                                 - ringkasan DM
                  Q&A saat di-mention                     - retensi data
```

## Instalasi

Prasyarat: [Hermes Agent](https://hermes-agent.nousresearch.com/docs/) sudah terinstal & terkonfigurasi, Python 3.11+, bot Telegram dari @BotFather (privacy mode **off**).

```bash
git clone <repo-url> && cd hackhaton-idhost
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example ~/.hermes/.env   # isi OPENAI_API_KEY, TELEGRAM_BOT_TOKEN, dst
```

Ikuti `deploy/README.md` untuk setup plugin Hermes, MCP server, cron job, dan gateway sebagai systemd service.

## Menjalankan

```bash
.venv/bin/python -m pytest tests/ -v      # unit test
.venv/bin/python eval/seed_group.py       # generate data evaluasi
.venv/bin/python eval/run_eval.py         # hitung recall/precision noise filter

systemctl status hermes-gateway            # cek status bot (kalau sudah dipasang sbg service)
```

## Struktur Proyek

```
ringkas/            # db.py, noise_filter.py, mcp_server.py, cron scripts
hermes/plugins/ringkas/  # plugin Hermes (mention gate, persona, command)
tests/               # unit test (pytest)
eval/                # data seed & script evaluasi recall/precision
docs/                # DECISIONS.md, AI_USAGE.md, EVAL.md
deploy/              # panduan deploy manual + wrapper script cron
```

## Dokumentasi

- [`PLAN.md`](PLAN.md) — rencana kerja harian (H1-H11)
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — keputusan arsitektur & bug yang ditemukan/diperbaiki
- [`docs/EVAL.md`](docs/EVAL.md) — hasil evaluasi recall/precision
- [`docs/AI_USAGE.md`](docs/AI_USAGE.md) — transparansi penggunaan Claude Code

## Keterbatasan & Rencana Lanjutan

- Belum ada dashboard web (diskip karena tekanan waktu submit — lihat gerbang keputusan H7 di `docs/DECISIONS.md`)
- Integrasi WhatsApp, voice note, dan multi-bahasa di luar cakupan versi ini
- Evaluasi baru mengukur akurasi penyaring noise, belum ekstraksi item LLM secara formal

## Lisensi & Tim

Dani ([mdaninas@gmail.com](mailto:mdaninas@gmail.com)) — IDwebhost AI Hackfest 2026.
