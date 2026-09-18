# DECISIONS — Catatan Keputusan Arsitektur

> Setiap keputusan penting dicatat di sini beserta alasannya, terutama saat dokumentasi resmi Hermes berbeda dari asumsi di `PLAN.md`.

## H1 — 2026-09-18/19: Provider LLM

**Keputusan:** Pakai OpenAI langsung (`gpt-5-mini`) via API key milik Dani, bukan OpenRouter atau Nous Portal seperti asumsi awal di `PLAN.md` bagian 2.

**Alasan:** Dani sudah punya API key OpenAI aktif. OpenRouter dan Nous Portal belum di-setup (belum ada akun/login). Daripada bikin akun baru untuk lomba, pakai yang sudah tersedia lebih cepat dan tetap sesuai aturan hemat resource (tidak menjalankan LLM lokal).

**Detail teknis penting (untuk siapa pun yang setup ulang VPS ini):**
- Provider id yang benar di config Hermes adalah `openai-api`, **bukan** `openai` — id `openai` ternyata alias built-in ke OpenRouter, bukan ke `api.openai.com` langsung.
- `~/.hermes/.env` di VPS ini sempat punya baris `OPENAI_BASE_URL=https://9router.jcamp.io/v1` (bawaan image/template VPS dari penyedia hosting, bukan disengaja) yang membelokkan semua request OpenAI ke router pihak ketiga. Baris ini sudah di-nonaktifkan (comment out).
- Provider `openai-api` mengirim parameter `reasoning.effort` secara default (transport-nya pakai OpenAI Responses API). Model non-reasoning seperti `gpt-4o-mini` menolak parameter ini (HTTP 400). Karena itu model default diset ke `gpt-5-mini` (mendukung reasoning params), bukan `gpt-4o-mini`.

**Config final** (`~/.hermes/config.yaml`):
```yaml
model:
  provider: openai-api
  default: gpt-5-mini
```

**Verifikasi:** `hermes -z "halo"` berhasil dibalas oleh model.

---

## H1 — 2026-09-18: Plan A vs Plan B (arsitektur bot Telegram)

**Keputusan: Plan A** — Hermes memegang bot Telegram sepenuhnya (tidak ada `collector.py` terpisah).

**Bot uji:** `@ringkasgrup_bot` (t.me/ringkasgrup_bot), privacy mode OFF.

**Hasil spike, tiga syarat `PLAN.md` bagian 3:**
1. ✅ Hermes menerima **semua** pesan grup (bukan hanya command/mention) — dikonfirmasi lewat log `[Telegram] Flushing text batch ...` untuk pesan biasa.
2. ✅ Hermes bisa diam kecuali di-mention — pakai `TELEGRAM_REQUIRE_MENTION=true` + `TELEGRAM_OBSERVE_UNMENTIONED_GROUP_MESSAGES=true`. Pesan tanpa mention masuk log sebagai `Telegram group message observed (no bot trigger)` dan **tidak** memicu panggilan LLM (tidak ada baris `conversation turn` / `API call` menyertainya) — jadi tidak kena biaya. Pesan dengan `@ringkasgrup_bot` memicu turn penuh dan bot membalas.
3. ✅ Biaya wajar — karena observed messages gratis (no LLM call), biaya hanya muncul saat bot benar-benar dipicu (mention, command, atau nanti cron ringkasan terjadwal), bukan per pesan masuk. Aman untuk grup ~300 pesan/hari.

**Konsekuensi untuk desain:** karena Plan A dipakai, MCP tool `simpan_pesan` (bagian 6 `PLAN.md`) perlu dipanggil dari dalam skill/context Hermes saat pesan "diobservasi", bukan dari service `collector.py` terpisah. Perlu diverifikasi lagi di H2/H3 bagaimana observed messages ini bisa diteruskan ke MCP tool penyimpanan.

**Konfigurasi Telegram final** (`~/.hermes/.env`):
```bash
TELEGRAM_BOT_TOKEN=<dari BotFather>
HERMES_TELEGRAM_DISABLE_FALLBACK_IPS=true   # VPS ini tidak punya IPv6 global; lihat catatan bug di bawah
TELEGRAM_GROUP_ALLOWED_CHATS=-5303407935    # chat ID grup uji
TELEGRAM_ALLOWED_CHATS=-5303407935
TELEGRAM_REQUIRE_MENTION=true
TELEGRAM_OBSERVE_UNMENTIONED_GROUP_MESSAGES=true
```

**Verifikasi:** dilakukan langsung di grup uji Telegram — pesan biasa "HALO" diobservasi tanpa balasan, pesan "@ringkasgrup_bot" mendapat balasan.

---

## H1 — 2026-09-18: Bug/isu environment yang ditemukan & fix-nya

Catatan untuk siapa pun yang setup ulang VPS ini dari image yang sama:

1. **`OPENAI_BASE_URL` bawaan template VPS** mengarah ke router pihak ketiga (`9router.jcamp.io`), membuat semua request OpenAI gagal dengan error membingungkan (`No active credentials for provider: openai`, lalu `API key required for remote API access`). Sudah dinonaktifkan (comment out) di `.env`.
2. **Provider id `openai` di Hermes adalah alias ke OpenRouter**, bukan ke `api.openai.com`. Provider id yang benar untuk OpenAI langsung adalah `openai-api`.
3. **Provider `openai-api` selalu kirim parameter `reasoning.effort`** (pakai OpenAI Responses API), yang ditolak model non-reasoning seperti `gpt-4o-mini` (HTTP 400). Model default diset ke `gpt-5-mini`.
4. **Gateway Telegram hang tanpa error saat startup** karena proses "discover fallback IPs via DNS-over-HTTPS" mencoba jalur IPv6 yang di-blackhole (VPS ini tidak punya IPv6 global), dan timeout internalnya tidak berhasil memutus thread yang macet (referensi ke isu upstream #87015 di kode Hermes). Fix: `HERMES_TELEGRAM_DISABLE_FALLBACK_IPS=true`.

**Peringatan tambahan dari Hermes sendiri (belum action item untuk H1, dicatat untuk nanti):** `hermes doctor`/security audit memperingatkan bahwa Hermes berjalan sebagai user **root** di VPS ini — risiko keamanan kalau ada prompt-injection atau endpoint yang exposed. Pertimbangkan menjalankan sebagai user non-root sebelum publik/demo (lihat juga catatan user `dani` terpisah yang sudah ada di VPS ini).
