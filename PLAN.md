# PLAN — Ringkas: Asisten Ringkasan Grup Chat (AI Hackfest 2026)

> Dokumen ini adalah rencana kerja untuk Claude Code yang berjalan di VPS.
> Pemilik proyek: Dani. Nama "Ringkas" adalah nama kerja dan boleh diganti.
> Aturan kerja ada di `CLAUDE.md`. Kerjakan per hari (H1–H11), verifikasi setiap langkah, lalu commit.

## Status Saat Ini

> Diperbarui oleh Claude Code setiap kali satu hari selesai atau ada keputusan penting.

- **Hari berjalan:** H2 (selesai)
- **Arsitektur:** Plan A dipilih — Hermes memegang bot Telegram sepenuhnya, tapi logika "simpan semua pesan + diam kecuali di-mention" dipindah ke plugin Hermes sendiri (`hermes/plugins/ringkas/`), bukan fitur observe bawaan Hermes yang ternyata tidak bisa diintersep. Lihat `docs/DECISIONS.md`.
- **Gerbang H7 (dashboard):** belum dievaluasi
- **Catatan terakhir:** `ringkas/db.py` (skema + FTS5) dan `ringkas/noise_filter.py` selesai dengan 16 unit test lulus. Pesan grup nyata sudah mulai tersimpan otomatis lewat plugin `pre_gateway_dispatch` sejak 19 Sep. MCP tool `simpan_pesan` juga terdaftar (dipakai plugin secara langsung, bukan lewat MCP call, demi performa). Item H1 opsional (cek Hermes terima foto) belum dikerjakan, tidak prioritas.

---

## 0. Konteks Lomba (jangan diabaikan)

- **Kompetisi:** IDwebhost AI Hackfest 2026, tema "Build Agent, Deliver Impact".
- **Kategori:** Productivity & Personal AI.
- **Framework wajib:** Hermes Agent (Nous Research).
- **VPS:** 4 core CPU, 4 GB RAM, 20 GB SSD. Model LLM dipanggil lewat API, bukan dijalankan lokal.
- **Batas submission:** 30 September 2026. Target internal: **submit 29 September**, dan 30 September hanya dipakai sebagai cadangan.
- **Yang dinilai juri:** relevansi masalah, efektivitas agent, kreativitas, kualitas teknis, dan komunikasi.
- **Yang dikirim:** video demo 3–5 menit (link publik) dan artikel minimal 800 kata.
- **Aturan penting:** penggunaan AI dalam pengembangan harus dijelaskan secara transparan di artikel. Catat di mana saja Claude Code dipakai.

**Prinsip utama:** agent yang benar-benar dipakai dan menyelesaikan masalah lebih penting daripada agent yang rumit. Setiap keputusan harus lolos pertanyaan ini: *apakah ini membuat demo lebih meyakinkan?*

---

## 1. Masalah & Solusi

**Masalah.** Grup chat (kelas anak, kantor, angkatan, RT) berisi ratusan pesan per hari, dan sebagian besar adalah noise: stiker, "siap", ucapan, forward. Pengumuman, tenggat, dan keputusan penting tenggelam di antaranya. Pengguna hanya punya dua pilihan buruk: membaca semuanya, atau mute grup lalu ketinggalan info.

**Solusi.** Bot asisten di grup Telegram yang:

1. membaca semua pesan grup dan menyaring noise;
2. mengirim **ringkasan terjadwal** berisi pengumuman, tenggat, keputusan, dan pertanyaan yang belum terjawab;
3. **mendeteksi tenggat** lalu mengirim **pengingat otomatis**;
4. **menjawab pertanyaan** tentang riwayat grup saat di-mention;
5. mengirim **ringkasan personal lewat DM** sesuai konteks tiap pengguna (memakai memori Hermes);
6. dilengkapi **dashboard web minimal** untuk statistik, riwayat/kalender, pengaturan, dan kontrol privasi.

**Kenapa Telegram, bukan WhatsApp.** Bot grup Telegram resmi dan aman. Bot WhatsApp tidak resmi berisiko membuat nomor diblokir. WhatsApp disebut di artikel sebagai target pengembangan berikutnya.

---

## 2. Tech Stack

| Bagian | Pilihan |
|---|---|
| Agent | Hermes Agent (instal lewat script resmi, provider LLM lewat OpenRouter atau Nous Portal) |
| Bahasa | Python 3.11+ |
| Database | SQLite (mode WAL), dengan FTS5 untuk pencarian pesan |
| Tools untuk agent | MCP server Python (SDK resmi `mcp`, FastMCP) |
| Bot Telegram (bila Plan B) | `python-telegram-bot` v21+ |
| Dashboard | FastAPI + Jinja2 + HTMX (via CDN) + CSS sederhana. **Tanpa React.** |
| Proses | systemd service untuk setiap komponen |
| Zona waktu | `Asia/Jakarta` (WIB) untuk semua jadwal dan tampilan |

**Aturan dependensi:** jangan menambah library berat. RAM hanya 4 GB, dan Hermes juga berjalan di VPS yang sama.

---

## 3. Arsitektur

```
Grup Telegram ──► [Penerima pesan] ──► SQLite (messages)
                                          ▲
                        MCP tools ────────┤
                            ▲             │
                     Hermes Agent         │
       (ringkas, ekstrak tenggat, Q&A,    │
        memori per grup & per user, cron) │
                            │             │
                            ▼             ▼
                 kirim pesan ke Telegram   Dashboard FastAPI
```

### ⚠️ Keputusan arsitektur di H1 (wajib diverifikasi, jangan diasumsikan)

Detail perilaku gateway Telegram Hermes di dalam grup **belum dipastikan**. Di H1, uji langsung lalu pilih salah satu rencana berikut.

**Plan A: Hermes memegang bot Telegram sepenuhnya.**
Pilih ini jika semua syarat berikut terpenuhi:
- Hermes bisa menerima **semua** pesan grup (setelah privacy mode bot dimatikan);
- Hermes bisa dikonfigurasi atau diinstruksikan untuk **diam** kecuali di-mention;
- biaya per pesan masuk wajar untuk grup berisi sekitar 300 pesan per hari.

Pada Plan A, setiap pesan disimpan lewat MCP tool `simpan_pesan`.

**Plan B: bot penerima milik sendiri, dan Hermes sebagai "otak".**
Pilih ini jika Plan A tidak memenuhi syarat di atas.
- Service Python (`collector`) memegang token bot, menyimpan semua pesan ke SQLite **tanpa memanggil LLM**, lalu meneruskan mention dan DM ke Hermes.
- Hermes membaca data lewat MCP tools dan mengirim balasan lewat tool `kirim_pesan` (Telegram Bot API `sendMessage`).
- Cek di dokumentasi Hermes cara memanggil agent secara terprogram, misalnya mode one-shot di CLI, API, atau RPC. Pilih cara yang paling sederhana dan stabil.

Catatan penting: satu token bot tidak boleh di-polling oleh dua proses sekaligus. Jika memakai Plan B, gateway Telegram Hermes **jangan** memakai token yang sama untuk polling.

Tulis keputusan beserta alasannya di `docs/DECISIONS.md`.

---

## 4. Struktur Repo

```
ringkas/
├── CLAUDE.md               # aturan kerja Claude Code (dimuat otomatis tiap sesi)
├── PLAN.md                 # dokumen ini
├── README.md
├── .env.example            # TELEGRAM_BOT_TOKEN, LLM keys, DASHBOARD_SECRET, dst.
├── docs/
│   ├── DECISIONS.md        # keputusan arsitektur + alasan
│   ├── AI_USAGE.md         # catatan penggunaan AI (untuk artikel)
│   └── EVAL.md             # hasil evaluasi & angka dampak
├── ringkas/
│   ├── db.py               # skema + helper SQLite
│   ├── noise_filter.py     # penyaring noise berbasis aturan
│   ├── mcp_server.py       # MCP tools untuk Hermes
│   ├── collector.py        # (Plan B) bot penerima pesan
│   ├── telegram_send.py    # helper kirim pesan
│   ├── jobs.py             # retensi data, pengingat (bila tidak lewat cron Hermes)
│   └── dashboard/
│       ├── app.py
│       ├── templates/
│       └── static/
├── hermes/
│   ├── context/            # SOUL.md / AGENTS.md: instruksi perilaku agent
│   └── skills/             # skill awal (format ringkasan, ekstraksi tenggat)
├── eval/
│   ├── seed_group.py       # generator grup simulasi + label "penting"
│   ├── labels.json
│   └── run_eval.py         # hitung recall/precision item penting
├── deploy/                 # file systemd
└── tests/
```

---

## 5. Model Data (SQLite)

- `groups` (id, telegram_chat_id, nama, jam_ringkasan, kata_kunci_penting JSON, retensi_hari default 7, aktif, created_at)
- `members` (id, telegram_user_id, nama_tampilan, dm_aktif, konteks_personal TEXT)
- `messages` (id, group_id, telegram_msg_id, sender_id, teks, jenis [text/photo/sticker/...], is_noise, reply_to, created_at). Tambahkan **FTS5** pada kolom `teks`.
- `summaries` (id, group_id, periode_mulai, periode_selesai, isi_markdown, jumlah_pesan, jumlah_penting, created_at)
- `items` (id, group_id, summary_id, tipe [pengumuman/tenggat/keputusan/pertanyaan], judul, detail, due_at NULL, source_msg_ids JSON, status [aktif/selesai/dibatalkan])
- `reminders` (id, item_id, kirim_pada, target [grup/user], terkirim)
- `magic_links` (token, telegram_user_id, group_id, expires_at, used)
- `stats_daily` (group_id, tanggal, pesan_masuk, pesan_noise, item_penting, tenggat_terdeteksi)

Hapus pesan mentah otomatis setelah `retensi_hari`. Ringkasan dan item tetap disimpan.

---

## 6. MCP Tools (kontrak awal)

| Tool | Fungsi |
|---|---|
| `simpan_pesan(chat_id, msg)` | (Plan A) simpan pesan + tandai noise |
| `ambil_pesan(group_id, sejak, sampai, tanpa_noise=True)` | pesan untuk diringkas |
| `cari_pesan(group_id, query, limit)` | pencarian FTS5 untuk Q&A |
| `simpan_ringkasan(group_id, periode, isi, items[])` | simpan ringkasan + item terstruktur |
| `tambah_tenggat(group_id, judul, due_at, source_msg_ids)` | buat item tenggat + jadwal pengingat |
| `daftar_tenggat(group_id, rentang)` | tenggat aktif |
| `ambil_pengaturan_grup(group_id)` / `ubah_pengaturan_grup(...)` | pengaturan |
| `kirim_pesan(chat_id, teks)` | kirim ke Telegram (Plan B) |
| `buat_magic_link(user_id, group_id)` | link dashboard sementara (berlaku 15 menit) |
| `hapus_data_grup(group_id)` | hapus semua data grup (kontrol privasi) |

Semua tool harus memvalidasi input dan mengembalikan pesan error yang jelas.

---

## 7. Spesifikasi Perilaku Agent

### Format ringkasan (bahasa Indonesia, ringkas)
```
📋 Ringkasan Grup <nama> — <tanggal>
<N> pesan hari ini, <M> yang penting.

📢 Pengumuman
• ...
⏰ Tenggat
• <apa> — <kapan, dalam WIB>
✅ Keputusan
• ...
❓ Belum terjawab
• ...
```
Bagian yang kosong tidak ditampilkan. Jika tidak ada yang penting, cukup kirim satu kalimat: "Tidak ada info penting hari ini."

### Aturan perilaku
- Di grup, bot **diam** kecuali di-mention atau menjalankan jadwal.
- Jangan pernah mengarang. Setiap item harus berasal dari pesan yang benar-benar ada (`source_msg_ids`).
- Pahami ekspresi waktu lokal: "besok", "Jumat depan", "paling lambat Kamis", "abis maghrib". Jika ekspresinya ambigu, tulis apa adanya dan jangan menebak jam.
- Saat pertama kali masuk grup, bot mengumumkan diri dan menjelaskan data apa yang disimpan serta berapa lama.

### Penyaring noise (berbasis aturan, sebelum masuk LLM)
Tandai `is_noise` untuk: stiker/GIF tanpa teks; pesan yang hanya berisi emoji; pesan pendek standar seperti "ok", "siap", "noted", "aamiin", "makasih", "wkwk", dan variasinya; ucapan standar (selamat ulang tahun, dan sejenisnya) **kecuali** memuat tanggal atau angka uang. Buat unit test untuk penyaring ini.

### Memori (pemanfaatan Hermes)
- **Per grup:** apa yang dianggap penting di grup ini (belajar dari koreksi, misalnya "iuran itu penting").
- **Per pengguna:** konteks personal untuk ringkasan DM (misalnya "anaknya ikut pramuka").
- Tunjukkan di demo bahwa agent **berubah perilaku** setelah dikoreksi. Ini momen kunci untuk juri.

---

## 8. Rencana Harian

> Setiap hari punya **Target** dan **Verifikasi**. Sebuah hari belum dianggap selesai sebelum semua verifikasinya lulus. Commit setiap milestone dengan pesan yang jelas.

### H1 — Minggu, 20 Sep: Fondasi & keputusan arsitektur
**Target**
- Instal Hermes (script resmi), jalankan `hermes setup` dan `hermes doctor`, lalu lakukan smoke test chat.
- Buat bot di @BotFather, **matikan privacy mode** (`/setprivacy` → Disable), dan buat grup uji.
- Spike: jalankan Plan A di grup uji dan jawab tiga syarat di bagian 3.
- Tulis `docs/DECISIONS.md` (Plan A atau B), inisialisasi repo sesuai struktur, dan buat `.env.example`.
- Cek juga apakah Hermes bisa menerima foto (vision), karena ini opsional untuk nanti.

**Verifikasi**
- [x] Hermes membalas di chat uji.
- [x] Bot menerima pesan biasa di grup (bukan hanya perintah).
- [x] Keputusan Plan A/B tercatat beserta alasannya.

### H2 — Senin, 21 Sep: Database & penerimaan pesan
**Target**
- `db.py` (skema lengkap + FTS5), `noise_filter.py` + unit test.
- Semua pesan grup tersimpan (lewat Plan A atau B).
- **Mulai uji coba di grup nyata hari ini** (dengan izin anggota), supaya data terkumpul sekitar 7 hari sebelum demo.

**Verifikasi**
- [x] Kirim pesan campuran → semuanya tersimpan, noise tertandai dengan benar. (5 pesan live di grup uji: ucapan, "ok", emoji, mention, obrolan biasa — semua benar. Target asli 20 pesan, dipersingkat karena tiap kategori sudah representatif dan tercakup 16 unit test.)
- [x] Unit test penyaring noise lulus. (16/16 lulus, `tests/test_noise_filter.py` + `tests/test_db.py`)

### H3 — Selasa, 22 Sep: MCP server & ringkasan manual
**Target**
- `mcp_server.py` dengan tool: `ambil_pesan`, `simpan_ringkasan`, `cari_pesan`, `ambil_pengaturan_grup`.
- Daftarkan MCP server ke Hermes (cek konfigurasi MCP di dokumentasi Hermes).
- Context file dan skill untuk format ringkasan.
- Perintah `/ringkas` di grup untuk memicu ringkasan manual.

**Verifikasi**
- [ ] `/ringkas` menghasilkan ringkasan sesuai format, dan setiap item punya `source_msg_ids` yang valid.
- [ ] Tidak ada item yang dikarang (cek manual 1 ringkasan).

### H4 — Rabu, 23 Sep: Tenggat & pengingat terjadwal
**Target**
- Ekstraksi tenggat → `tambah_tenggat` → jadwal pengingat (H-1 dan hari-H pagi, WIB).
- Ringkasan otomatis harian lewat cron Hermes (default jam 20.00 WIB, bisa diatur per grup).

**Verifikasi**
- [ ] Pesan "iuran 50rb paling lambat Kamis" → item tenggat dengan tanggal yang benar.
- [ ] Pengingat terkirim tepat waktu (uji dengan jadwal beberapa menit ke depan).
- [ ] Ringkasan harian terkirim otomatis.

### H5 — Kamis, 24 Sep: Tanya jawab riwayat grup
**Target**
- Saat di-mention: ambil pesan relevan lewat `cari_pesan` (FTS5) plus konteks sekitarnya, lalu jawab dengan menyebut sumbernya.
- Jika tidak ditemukan, jawab jujur: "Aku tidak menemukan info itu di grup."

**Verifikasi**
- [ ] 5 pertanyaan uji terhadap data seed dijawab benar.
- [ ] 2 pertanyaan tentang hal yang tidak ada di grup → bot mengaku tidak tahu, tidak mengarang.

### H6 — Jumat, 25 Sep: Ringkasan personal (DM) + evaluasi
**Target**
- Pengguna mengaktifkan DM (`/start` di chat pribadi), bot menyimpan konteks personal, lalu mengirim ringkasan DM yang menyorot hal relevan.
- Memori per grup: koreksi pengguna ("ini penting", "ini tidak penting") memengaruhi ringkasan berikutnya.
- `eval/seed_group.py`: grup simulasi realistis berbahasa Indonesia (sekitar 250 pesan, sekitar 20 item penting berlabel).
- `eval/run_eval.py`: hitung recall dan precision item penting.

**Verifikasi**
- [ ] Dua pengguna dengan konteks berbeda menerima ringkasan DM yang berbeda.
- [ ] Setelah dikoreksi, perilaku agent berubah pada ringkasan berikutnya.
- [ ] Hasil evaluasi pertama tercatat di `docs/EVAL.md`.

### H7 — Sabtu, 26 Sep: Stabilisasi, privasi, dan **GERBANG KEPUTUSAN**
**Target**
- Pesan perkenalan saat bot masuk grup, `/hapusdata` (khusus admin), job retensi data.
- Perbaiki bug dari uji coba grup nyata, lalu jalankan ulang evaluasi.
- Pasang semua komponen sebagai systemd service agar tetap hidup setelah reboot.

**GERBANG:** jika fitur H3–H6 **belum stabil**, lewati dashboard. Sebagai gantinya, buat perintah `/statistik` di chat, lalu langsung lompat ke H9.

**Verifikasi**
- [ ] VPS di-reboot → semua service hidup kembali.
- [ ] `/hapusdata` benar-benar menghapus data grup.
- [ ] Recall pada evaluasi mencapai sekitar 80% atau lebih (jika belum, perbaiki prompt/skill dulu, jangan ke dashboard).

### H8 — Minggu, 27 Sep: Dashboard minimal
**Target** (hanya jika lolos gerbang H7)
- Login lewat magic link: `/dashboard` di DM → link sekali pakai yang berlaku 15 menit.
- Halaman **Statistik**: pesan masuk, noise, item penting, tenggat, estimasi waktu hemat. Asumsi hitungan (misalnya waktu baca per pesan) ditulis jelas di halaman.
- Halaman **Riwayat & Kalender tenggat**.
- Halaman **Pengaturan** (jam ringkasan, kata kunci penting, retensi) + tombol hapus data.
- Tampilan sederhana, rapi, dan responsif di HP.

**Verifikasi**
- [ ] Link kedaluwarsa dan link bekas tidak bisa dipakai.
- [ ] Mengubah jam ringkasan di dashboard → jadwal berubah.
- [ ] Angka statistik cocok dengan data di DB.

### H9 — Senin, 28 Sep: Pemolesan & bekukan fitur
**Target**
- Perbaiki bug, jalankan evaluasi final, lengkapi `docs/EVAL.md` dengan angka final.
- Lengkapi `README.md` (cara instal & menjalankan) dan `docs/AI_USAGE.md`.
- Siapkan data demo yang bersih (grup "Orang Tua Kelas 3B" dari seed).
- **Bekukan fitur di akhir hari.** Tidak ada fitur baru setelah ini.

**Verifikasi**
- [ ] Skenario demo (bagian 9) berjalan mulus 3 kali berturut-turut.

### H10 — Selasa, 29 Sep: Video, artikel, SUBMIT
**Target**
- Rekam video 3–5 menit sesuai skenario, unggah ke YouTube dengan akses publik/unlisted (tanpa password).
- Tulis artikel minimal 800 kata (struktur di bagian 10).
- **Submit hari ini.**

**Verifikasi**
- [ ] Link video bisa dibuka dari browser incognito.
- [ ] Artikel minimal 800 kata dan memuat bagian penggunaan AI.
- [ ] Nama proyek, nama anggota, dan kategori tercantum.

### H11 — Rabu, 30 Sep: Cadangan
Hanya untuk memperbaiki submission jika ada masalah. Tidak ada koding fitur.

---

## 9. Skenario Demo (video)

1. **Hook (0:00–0:30):** grup dengan 247 pesan belum dibaca. "Berapa yang penting? Tiga."
2. **Masalah (0:30–1:00):** scroll cepat berisi stiker, ucapan, dan obrolan santai.
3. **Ringkasan (1:00–1:45):** ringkasan malam masuk, rapi dan singkat.
4. **Tanya jawab (1:45–2:15):** "@bot study tour bayar berapa?" → jawaban beserta sumbernya.
5. **Proaktif (2:15–2:45):** pengingat tenggat masuk dengan sendirinya.
6. **Belajar (2:45–3:30):** koreksi "iuran itu penting" → ringkasan berikutnya berubah, dan dua orang tua menerima ringkasan DM yang berbeda.
7. **Dashboard & dampak (3:30–4:15):** statistik, angka evaluasi, kontrol privasi.
8. **Penutup (4:15–4:45):** "Mute grupnya, biar agent yang membaca." Sebut WhatsApp sebagai langkah berikutnya.

---

## 10. Struktur Artikel (minimal 800 kata)

1. Latar belakang masalah (grup chat berisik, pengalaman nyata)
2. Solusi & cara kerja (fitur utama)
3. Arsitektur AI Agent (diagram, peran Hermes: memori, skill, cron, MCP)
4. Privasi & etika (pengumuman diri, retensi, hapus data)
5. Hasil & dampak (angka dari `docs/EVAL.md` dan uji coba grup nyata)
6. Keterbatasan & rencana lanjutan (WhatsApp, voice note, dll.)
7. Transparansi penggunaan AI (dari `docs/AI_USAGE.md`)

---

## 11. Di Luar Cakupan (JANGAN dikerjakan sebelum submit)

- Integrasi WhatsApp
- Voice note / speech-to-text
- Multi-bahasa selain Indonesia
- Sistem akun/registrasi dengan password
- Frontend framework (React, Vue, dll.)
- Model LLM lokal

---

## 12. Aturan Kerja

Aturan kerja untuk Claude Code ada di `CLAUDE.md` di root repo, supaya tidak ada dua versi aturan yang berbeda. Jika ada yang bertentangan antara dokumen ini dan `CLAUDE.md`, ikuti `CLAUDE.md` dan beri tahu Dani.
