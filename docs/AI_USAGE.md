# AI_USAGE — Catatan Penggunaan AI

> Dicatat sambil jalan untuk transparansi di artikel lomba. Setiap entri: hari, apa yang dikerjakan Claude Code, dan sejauh mana (dibuat penuh / dibantu / direview).

## H1 — 2026-09-18/19: Fondasi & keputusan arsitektur

- **Setup VPS & Hermes:** Claude Code mendiagnosis dan memperbaiki beberapa masalah konfigurasi Hermes Agent bawaan VPS (routing LLM yang salah, model/provider tidak cocok, gateway Telegram hang karena isu IPv6) — dibuat penuh oleh Claude Code, diverifikasi lewat smoke test dan log real-time.
- **Riset dokumentasi:** Claude Code membaca source code Hermes Agent yang terinstal lokal (bukan cuma dokumentasi web) untuk memverifikasi perilaku provider LLM dan gateway Telegram, setelah mendeteksi konten mencurigakan (kemungkinan prompt injection) di hasil fetch dokumentasi web resmi.
- **Konfigurasi gateway Telegram:** Claude Code menemukan dan menerapkan kombinasi env var yang tepat (`TELEGRAM_GROUP_ALLOWED_CHATS`, `TELEGRAM_REQUIRE_MENTION`, `TELEGRAM_OBSERVE_UNMENTIONED_GROUP_MESSAGES`) agar bot bisa membaca semua pesan grup tapi hanya membalas saat di-mention — dibuat penuh oleh Claude Code, diverifikasi langsung oleh Dani di Telegram.
- **Nama bot:** Claude Code mengusulkan beberapa opsi nama bot Telegram; Dani memilih dan mendaftarkan `ringkasgrup_bot` di @BotFather sendiri.
- **Dokumentasi keputusan:** `docs/DECISIONS.md` (Plan A vs Plan B, konfigurasi final, catatan bug environment) ditulis oleh Claude Code berdasarkan hasil spike test bersama Dani.
