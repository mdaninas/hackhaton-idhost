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

---

## H2 — 2026-09-19: `TELEGRAM_OBSERVE_UNMENTIONED_GROUP_MESSAGES` tidak bisa dipakai untuk penyimpanan pesan

**Temuan penting.** Fitur bawaan Hermes `TELEGRAM_REQUIRE_MENTION` + `TELEGRAM_OBSERVE_UNMENTIONED_GROUP_MESSAGES` (dipakai di H1) ternyata bekerja di dalam **adapter Telegram**, bukan lewat jalur gateway generik. Pesan yang "diobservasi" langsung ditulis ke transcript sesi lewat `store.append_to_transcript(...)` di dalam `plugins/platforms/telegram/adapter.py`, lalu `return` -- **tidak pernah** melewati `GatewayRunner._handle_message()`, tempat hook plugin `pre_gateway_dispatch` seharusnya fire. Akibatnya, tidak ada cara bagi plugin/tool apa pun untuk "melihat" pesan yang diobservasi ini secara real-time.

**Keputusan:** matikan `TELEGRAM_REQUIRE_MENTION`/`TELEGRAM_OBSERVE_UNMENTIONED_GROUP_MESSAGES` (di-comment di `.env`), dan pindahkan **seluruh** logika "simpan semua pesan + diam kecuali di-mention" ke plugin Hermes sendiri (`hermes/plugins/ringkas/`, di-symlink ke `~/.hermes/plugins/ringkas/`) lewat hook `pre_gateway_dispatch`:
1. Setiap pesan grup masuk -> disimpan ke `messages` (dengan noise tagging), rule-based, **tanpa panggil LLM**.
2. Kalau pesan tidak mention bot (dan bukan reply ke bot) -> return `{"action": "skip", "reason": "ringkas-ambient-observed"}`, gateway tidak dispatch ke agent.
3. Kalau mention/reply -> return `None`, dispatch normal jalan seperti biasa.

Hasilnya secara perilaku user **sama persis** dengan target awal (bot diam kecuali di-mention, biaya wajar), tapi implementasinya di plugin kita sendiri, bukan fitur bawaan Hermes -- supaya penyimpanan pesan mentah terjamin jalan untuk semua pesan.

**Bug lain yang ditemukan & diperbaiki saat membangun plugin ini:**
- `ringkas/db.py`: `get_connection()` tidak pernah memanggil `init_db()`, jadi tabel `messages` dkk baru ada kalau seseorang secara eksplisit memanggil `init_db()` duluan (di tes, ini otomatis lewat fixture; di plugin/live gateway, tidak). Fix: `init_db(conn)` sekarang dipanggil otomatis di dalam `get_connection()` (idempoten, `CREATE TABLE IF NOT EXISTS`).
- Perbandingan `source.platform != "telegram"` di plugin salah -- `source.platform` adalah `Platform` enum (`gateway/config.py`), bukan string, jadi perbandingan langsung selalu `True` (tidak pernah match) dan fungsi `return` lebih awal tanpa menyimpan apa pun. Fix: bandingkan `source.platform.value`.

**Cara restart gateway yang aman (dicatat karena berkali-kali salah saat debugging):** `pkill -f "hermes gateway run"` mengembalikan exit code 1 kalau tidak ada proses yang cocok, dan itu bisa menghentikan rangkaian perintah shell. Selalu beri `|| true`, dan jalankan `nohup hermes gateway run > logfile 2>&1 & disown` sebagai command terpisah dari `pkill`, jangan digabung satu baris.

**Verifikasi:** 4 pesan campuran (ucapan, "ok", emoji, mention) dikirim ke grup uji -> tersimpan semua dengan noise tag benar, dan hanya pesan mention yang dijawab bot (`pre_gateway_dispatch skip: reason=ringkas-ambient-observed` untuk 3 pesan lain, konfirmasi tidak ada panggilan LLM untuk itu).

---

## H3 — 2026-09-19: MCP tools lengkap + perintah `/ringkas`

**Ditambahkan ke `ringkas/db.py` dan `ringkas/mcp_server.py`:** `ambil_pesan`, `cari_pesan` (FTS5), `simpan_ringkasan`, `tambah_item`, `ambil_pengaturan_grup`. Semua tool MCP menerima `chat_id` (Telegram chat id, string) secara konsisten, bukan id internal — supaya agent tidak perlu tahu skema database internal saat memanggilnya lewat percakapan biasa (mis. Q&A saat di-mention, disiapkan untuk H5).

**Perintah `/ringkas`:** diimplementasikan sebagai slash command plugin (`ctx.register_command`), BUKAN lewat MCP tool call dari agent. Alasan: `ctx.register_command`'s handler cuma menerima `raw_args: str` -- tidak ada akses ke sesi percakapan/chat context sama sekali, dan `ctx.inject_message()` (cara lain memicu turn agent) butuh `session_key` gateway yang juga tidak tersedia di handler slash command. Jadi `/ringkas` memakai `ctx.llm.complete_structured()` -- satu panggilan LLM one-shot dengan JSON schema untuk ekstrak item (bukan turn multi-tool seperti biasa), lalu markdown ringkasan dirakit sendiri oleh kode Python dari item-item itu (skeleton format dikontrol kode, bukan LLM), dan disimpan langsung lewat `ringkas/db.py` (bukan lewat MCP call).

**Cara plugin tahu chat_id saat ini:** hook `pre_gateway_dispatch` (yang sudah ada dari H2) fire untuk SETIAP pesan termasuk pesan `/ringkas` itu sendiri, sebelum command di-dispatch -- jadi plugin menyimpan `chat_id`/`chat_name` pesan terakhir ke variabel module-level (`_LAST_CHAT_ID`), lalu command handler membacanya. Cukup aman untuk skala satu grup uji hackathon ini; kalau nanti multi-grup dengan trafik bersamaan, perlu diganti `contextvars.ContextVar` atau cara yang benar-benar per-request.

**Command Telegram (termasuk `/ringkas`) punya jalur otorisasi sendiri:** `_handle_command` di adapter Telegram Hermes memanggil `_should_process_message(msg, is_command=True)` dan `_is_user_authorized_from_message(msg)` SEBELUM event sampai ke `pre_gateway_dispatch` -- terpisah dari jalur pesan teks biasa. Karena `TELEGRAM_REQUIRE_MENTION` sudah dimatikan sejak H2, ini tidak masalah (semua command lolos), tapi penting diketahui kalau nanti mau membatasi siapa yang boleh pakai `/ringkas`.

**Anti-mengarang:** setiap item dari LLM difilter lagi di kode -- `source_msg_ids` yang tidak ada di set pesan yang benar-benar diambil (`ambil_pesan`) dibuang, dan item tanpa `source_msg_ids` valid atau tanpa judul di-drop seluruhnya sebelum disimpan/ditampilkan.

**Verifikasi:** 6 pesan dikirim ke grup uji (4 penting: pengumuman/tenggat/keputusan/pertanyaan, 2 noise: "ok" + emoji) -> `/ringkas` menghasilkan markdown sesuai format `PLAN.md` bagian 7 persis, 4 item tersimpan dengan `source_msg_ids` yang semuanya valid (merujuk pesan 1-4), 2 pesan noise tidak muncul di ringkasan sama sekali.

---

## H4 — 2026-09-19: Tenggat, pengingat, dan ringkasan harian otomatis

**Ekstraksi tenggat dengan tanggal pasti:** skema JSON untuk item `tenggat` diubah dari teks bebas (`due_at_wib`) menjadi `due_date_wib` ("YYYY-MM-DD", WIB) + `due_time_wib` opsional. LLM diberi konteks "hari ini adalah <nama hari>, <tanggal>" di instruksi supaya bisa menghitung tanggal relatif ("Kamis", "Jumat depan") jadi tanggal pasti. Kalau LLM tidak bisa memastikan tanggalnya, dia diinstruksikan mengosongkan `due_date_wib` dan pakai tipe "pengumuman" saja -- tidak menebak.

**Penjadwalan pengingat:** fungsi baru `ringkas.db.simpan_tenggat_dengan_pengingat()` -- sekali dipanggil, langsung membuat item tenggat DAN menjadwalkan 2 pengingat (H-1 jam 08:00 WIB, hari-H jam 07:00 WIB), tapi HANYA yang waktunya masih di masa depan (supaya deadline yang sudah lewat tidak memicu reminder "terlambat" beruntun saat job pertama kali jalan). Dipakai baik oleh `/ringkas` (plugin) maupun `ringkas/daily_summary.py` (cron) -- satu sumber logika.

**Anti-mengarang diperkuat di level MCP server:** tool `simpan_ringkasan` sekarang memvalidasi `source_msg_ids` tiap item terhadap SEMUA pesan grup (bukan cuma periode tertentu) lewat `pesan_ids_valid()`, dan membuang item tanpa judul atau tanpa id valid -- ini melindungi jalur agent (mention/percakapan biasa yang manggil MCP tool langsung), bukan cuma jalur `/ringkas` yang sudah divalidasi sendiri di plugin.

**Ringkasan harian: kenapa `no_agent` script, bukan agent job biasa.** Awalnya dicoba agent cron job (prompt instruksikan panggil MCP tool `ambil_pesan`/`simpan_ringkasan`), tapi ternyata **Hermes tidak otomatis menyuntikkan tanggal/jam saat ini ke system prompt** -- dokumentasi Hermes sendiri bilang agent harus pakai tool `terminal` (`date`) kalau perlu tahu waktu sekarang, dan itu tidak reliable untuk cron job yang jadwalnya sama setiap hari tapi butuh tahu "hari ini" yang berbeda-beda. Solusi: `ringkas/daily_summary.py`, cron job `--no-agent`, panggil OpenAI langsung (bukan lewat `ctx.llm`, karena itu cuma ada di dalam plugin, tidak di script standalone) memakai kredensial yang dibaca manual dari `~/.hermes/.env` (bukan `os.environ` -- env subprocess cron `no_agent` disanitasi, secret provider tidak diwariskan). Logikanya sengaja meniru persis `/ringkas` di plugin supaya hasilnya konsisten.

**Bug ditemukan saat build `daily_summary.py`:** panggilan OpenAI chat completions dengan `temperature: 0` ditolak (`HTTP 400: Unsupported value: 'temperature' does not support 0 with this model. Only the default (1) value is supported.`) untuk `gpt-5-mini` di endpoint ini. Parameter `temperature` dihapus dari request (pakai default).

**Pengingat: kenapa juga `no_agent` script, baca token langsung dari file.** `ringkas/send_reminders.py`, cron job `--no-agent` tiap 5 menit, kirim lewat Telegram Bot API langsung (`ringkas/telegram_client.py`, stdlib `urllib` saja, tanpa dependency baru) -- sama sekali tidak butuh LLM untuk sekadar cek tabel `reminders` dan kirim pesan template.

**Script cron HARUS ada fisik di `~/.hermes/scripts/`, symlink ditolak.** Percobaan pertama pakai symlink dari `~/.hermes/scripts/` ke file di repo (pola yang sama seperti plugin di H2) ditolak Hermes: `"Script path escapes the scripts directory via traversal"` -- ada guard keamanan yang resolve symlink dan cek hasilnya masih di dalam direktori scripts. Solusi: file fisik kecil (wrapper) di `~/.hermes/scripts/` yang cuma `sys.path.insert` ke `/root/hackhathon` lalu `import` dan panggil fungsi `main()` dari modul aslinya di repo -- source of truth logika tetap di repo, cuma file pemicu (2-3 baris) yang harus fisik di luar.

**Gap yang disadari, belum dikerjakan:** `daily_summary.py` memproses SEMUA grup di tabel `groups` dengan `aktif=1` pada jam yang SAMA (13:00 UTC / 20:00 WIB, hardcode), belum baca `jam_ringkasan` per grup dari `ambil_pengaturan_grup()`. Cukup untuk 1 grup uji sekarang; kalau nanti ada banyak grup dengan jam ringkasan berbeda-beda, perlu job generator dinamis atau job per-grup.

**Verifikasi:**
- Pesan "Iuran study tour 250rb paling lambat Jumat tanggal 25" (dikirim 19 Sept, Sabtu) -> `due_at` tersimpan tepat `2026-09-24T17:00:00+00:00` (= 25 Sept 00:00 WIB, benar).
- 2 pengingat terjadwal otomatis: `2026-09-24T01:00:00+00:00` (H-1, 08:00 WIB) dan `2026-09-25T00:00:00+00:00` (hari-H, 07:00 WIB) -- kedua waktu dihitung benar.
- Pengingat uji dengan jadwal 2 menit ke depan: terkirim tepat waktu (dites manual dan lewat cron asli Hermes, `last_status: ok`, tick `every 5m` berjalan sesuai jadwal).
- `ringkas/daily_summary.py` dites manual end-to-end: pesan ringkasan masuk ke grup Telegram, item + tenggat + pengingat tersimpan benar di database. Terdaftar sebagai cron job (`ringkas-daily-summary`, jam 20:00 WIB) untuk pengiriman otomatis besok dan seterusnya.

---

## H5 — 2026-09-19: Tanya jawab riwayat grup

**Bug ditemukan: deteksi mention di plugin (sejak H2) tidak reliable.** `_simpan_pesan_masuk` mengecek mention lewat regex `@ringkasgrup_bot` terhadap `event.text`. Ternyata di kode adapter Telegram Hermes (`_handle_text_message`), `event.text = self._clean_bot_trigger_text(event.text)` dipanggil dan MEMBERSIHKAN teks "@botusername" dari `event.text` SEBELUM event itu sampai ke hook `pre_gateway_dispatch` kita -- untuk semua pesan teks, bukan cuma command. Pesan uji H2/H3 yang isinya CUMA "@ringkasgrup_bot" (tanpa teks lain) kebetulan tetap ke-dispatch dengan benar sebelumnya (belum jelas persis mekanismenya, mungkin ada jalur lain yang kena), tapi begitu diuji dengan pertanyaan sungguhan setelah mention ("@ringkasgrup_bot kapan bayar iuran?") baru ketahuan: `event.text` yang diterima hook cuma "kapan bayar iuran?" (mention-nya sudah hilang), jadi regex `@ringkasgrup_bot` tidak akan pernah match.

**Fix:** `_pesan_mention_bot(event)` baca `event.raw_message.entities` (objek Telegram asli, python-telegram-bot `Message.entities`) langsung -- cari entity bertipe `"mention"` yang substring-nya (dihitung dari `offset`/`length` di TEKS ASLI `raw_message.text`) sama dengan `@ringkasgrup_bot`. Ini meniru cara Hermes sendiri mendeteksi mention (`_message_mentions_bot` di adapter), tapi diimplementasikan di plugin kita karena kita menggantikan seluruh logika require_mention bawaan Hermes (lihat H2).

**Persona 'Ringkas' via `ctx.register_system_prompt_section()`.** Tanpa ini, agent memakai persona Hermes default ("asisten umum") saat di-mention -- diuji langsung: ditanya "kapan bayar iuran study tour?" agent malah menjawab seperti asisten pribadi ("mau saya bantu tulis pesan ke penyelenggara?"), sama sekali tidak mencari ke riwayat grup sendiri. Solusinya: section system prompt baru (`ringkas.persona`, posisi `after_memory`, khusus platform telegram) yang eksplisit menyuruh agent (1) panggil `cari_pesan`/`ambil_pesan` dengan `chat_id` grup saat ini SEBELUM menjawab pertanyaan tentang grup, (2) sebutkan sumbernya, (3) kalau tidak ketemu, jawab jujur "Aku tidak menemukan info itu di grup." -- jangan mengarang, (4) jangan menawarkan bikin pesan ke pihak lain (perilaku asisten-umum yang tidak relevan). Section ini hanya berlaku untuk SESI BARU (dibangun sekali per sesi) -- sesi yang sudah berjalan lama sebelum plugin diupdate perlu di-`/new` dulu supaya persona baru kepakai.

**Chat_id untuk system prompt section:** `session_info` yang diterima callable section (`session_id`, `model`, `provider`, `platform`, `profile_name`, `cwd`) TIDAK menyertakan chat_id. Dipakai `_LAST_CHAT_ID` (variabel module-level yang sama dari H3) sebagai workaround -- valid untuk skala satu grup uji karena hook `pre_gateway_dispatch` selalu sempat update variabel itu untuk pesan yang memicu sesi baru, sebelum system prompt section-nya dibangun.

**Verifikasi live:**
- "kapan bayar iuran study tour?" (setelah `/new` + mention) -> agent panggil `mcp__ringkas__cari_pesan`, jawab: "Iuran study tour: Rp250.000 — paling lambat Jumat, tanggal 25. Sumber: pesan Muhammad, 2026-09-19 15:01:23 UTC." -- benar dan menyebut sumber valid.
- "siapa ketua kelasnya?" (info yang tidak ada di grup) -> agent panggil `cari_pesan` (hasil kosong), jawab: "Aku tidak menemukan info itu di grup." -- persis sesuai spesifikasi, tidak mengarang.
