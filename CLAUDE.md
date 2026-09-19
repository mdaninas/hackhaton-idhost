# Ringkas — Asisten Ringkasan Grup Chat (AI Hackfest 2026)

Bot Telegram berbasis **Hermes Agent** yang membaca grup chat, menyaring noise, lalu mengirim ringkasan terjadwal, mendeteksi tenggat dan mengirim pengingat, menjawab pertanyaan tentang riwayat grup, dan mengirim ringkasan personal lewat DM. Proyek ini untuk lomba IDwebhost AI Hackfest 2026, kategori Productivity & Personal AI. **Batas submit: 30 September 2026, target internal 29 September.**

Pemilik proyek: Dani (fresh graduate, terbiasa dengan Python dan SQL).

## Setiap memulai sesi

1. Baca bagian **"Status Saat Ini"** di `PLAN.md` untuk mengetahui hari berjalan (H1–H11).
2. Baca bagian hari tersebut di `PLAN.md` bagian 8. Buka bagian lain dari `PLAN.md` hanya jika dibutuhkan (arsitektur, model data, MCP tools, spesifikasi perilaku).
3. Cek `docs/DECISIONS.md` (jika sudah ada) untuk keputusan yang sudah diambil.
4. Sampaikan ke Dani secara singkat: hari berjalan, target hari ini, dan langkah pertama yang akan dikerjakan.

## Aturan kerja

1. **Verifikasi, jangan asumsi.** Untuk semua hal tentang Hermes Agent (konfigurasi MCP, gateway Telegram, cron, context file, skill), baca dulu dokumentasi resmi di https://hermes-agent.nousresearch.com/docs/ atau repo resminya. Jika dokumentasi berbeda dengan `PLAN.md`, dokumentasi yang menang. Catat perbedaannya di `docs/DECISIONS.md`.
2. **Langkah kecil, verifikasi, commit.** Selesaikan satu target, jalankan verifikasinya, tunjukkan hasilnya ke Dani, lalu commit. Jangan menggabungkan banyak target dalam satu langkah besar.
3. **Kerjakan hanya target hari berjalan.** Jangan mengerjakan fitur dari hari berikutnya atau dari daftar "Di Luar Cakupan" (`PLAN.md` bagian 11) tanpa persetujuan Dani.
4. **Perbarui progres.** Setelah semua verifikasi satu hari lulus, centang checklist di `PLAN.md`, perbarui "Status Saat Ini", lalu commit dengan pesan `chore(plan): selesai Hx`.
5. **Tanya dulu sebelum tindakan destruktif:** menghapus data, reset database, `git push --force`, menghapus file, atau mengubah konfigurasi sistem VPS (firewall, user, service di luar proyek ini).
6. **Rahasia.** Semua token dan API key disimpan di `.env` (sudah ada di `.gitignore`). Jangan pernah commit `.env`, menampilkan isinya, atau menulis token ke log. Perbarui `.env.example` setiap kali ada variabel baru, tanpa nilai aslinya.
7. **Hemat resource.** VPS hanya punya 4 GB RAM yang dipakai bersama oleh Hermes dan semua service. Jangan menambah dependensi berat dan jangan menjalankan model LLM lokal. Cek RAM (`free -h`) jika ada service baru.
8. **Pisahkan commit kosmetik dan struktural.** Perubahan format atau gaya tidak dicampur dengan perubahan logika atau struktur dalam satu commit.
9. **Catat penggunaan AI** di `docs/AI_USAGE.md` sambil jalan: bagian mana yang dibuat atau dibantu Claude Code. Catatan ini wajib untuk artikel lomba.
10. **Prioritas saat waktu mepet:** agent inti yang stabil > evaluasi dan angka dampak > fitur privasi > dashboard > pemolesan tampilan.

## Cara berkomunikasi dengan Dani

- Gunakan **bahasa Indonesia**.
- Jelaskan konsep yang mungkin baru secara singkat saat pertama kali muncul (misalnya privacy mode bot Telegram, MCP, FTS5, systemd).
- Beri langkah verifikasi yang bisa Dani jalankan sendiri, misalnya perintah dan hasil yang diharapkan.
- Jika ada istilah atau kebutuhan yang ambigu, tanyakan dulu. Jangan menebak.
- Jika sebuah target ternyata tidak realistis untuk harinya, katakan terus terang dan usulkan pemotongan cakupan.

## Konvensi kode

- Python 3.11+, type hints, fungsi kecil, docstring singkat.
- Semua waktu disimpan dalam UTC di database dan ditampilkan dalam WIB (`Asia/Jakarta`).
- Teks yang dilihat pengguna (pesan bot, dashboard) dalam bahasa Indonesia.
- Konfigurasi dibaca dari environment variable, tanpa nilai hardcode.
- Tes menggunakan `pytest`, di folder `tests/`.

## Perintah proyek

- **Setup:** `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- **Jalankan test:** `.venv/bin/python -m pytest tests/ -v`
- **Jalankan gateway Hermes (manual, foreground):** `hermes gateway run` (Ctrl+C untuk stop). Restart aman: `pkill -f "hermes gateway run" || true` lalu `nohup hermes gateway run > /tmp/gateway.log 2>&1 & disown` sebagai command terpisah (jangan digabung satu baris dengan pkill — lihat `docs/DECISIONS.md` bagian H2).
- **Cek status gateway:** `hermes gateway status`
- **Cek isi database:** `.venv/bin/python -c "import sqlite3; c=sqlite3.connect('data/ringkas.db'); [print(r) for r in c.execute('SELECT * FROM messages')]"`
- **Plugin Hermes** (`hermes/plugins/ringkas/`) di-symlink ke `~/.hermes/plugins/ringkas/` — edit langsung di repo, tidak perlu copy ulang, tapi tetap perlu restart gateway supaya perubahan kepakai.
- **MCP server** (`ringkas/mcp_server.py`, tool `simpan_pesan`) sudah terdaftar ke Hermes lewat `hermes mcp add ringkas ...` (config di `~/.hermes/config.yaml`, bukan di repo).
