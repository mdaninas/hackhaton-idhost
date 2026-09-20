# Ringkas: Asisten AI yang Membaca Grup Chat Supaya Kamu Tidak Perlu

**IDwebhost AI Hackfest 2026 — Kategori Productivity & Personal AI**

## 1. Latar Belakang Masalah

Hampir semua orang Indonesia yang aktif secara sosial punya setidaknya satu grup chat yang isinya ratusan pesan sehari: grup orang tua kelas anak, grup kantor, grup angkatan kuliah, grup RT. Sebagian besar isinya adalah noise — stiker, "ok", ucapan selamat, forward berantai. Tapi di antara noise itu, ada pengumuman penting, tenggat pembayaran, keputusan bersama, dan pertanyaan yang butuh jawaban.

Masalahnya, tidak ada jalan tengah. Kalau kamu rajin membaca semuanya, waktumu habis untuk menyaring sampah. Kalau kamu mute grupnya karena capek, kamu ketinggalan info yang benar-benar penting — kadang sampai kena denda telat bayar iuran, atau baru tahu ada acara sekolah setelah acaranya lewat.

Ringkas dibangun untuk menghilangkan pilihan buruk itu. Idenya sederhana: biarkan agent AI yang membaca semuanya, kamu cukup baca ringkasannya.

## 2. Solusi & Cara Kerja

Ringkas adalah bot Telegram yang bergabung ke grup chat dan diam-diam membaca semua pesan. Setiap pesan disaring lebih dulu dengan aturan sederhana (bukan LLM, supaya cepat dan gratis) — stiker tanpa keterangan, ucapan singkat seperti "siap"/"noted", emoji saja, dan basa-basi lain otomatis ditandai sebagai noise dan tidak ikut diringkas.

Setiap malam jam 20:00 WIB, Ringkas mengirim ringkasan otomatis berisi empat kategori: pengumuman, tenggat, keputusan, dan pertanyaan yang belum terjawab. Kalau ada tenggat waktu yang terdeteksi (misalnya "iuran 50rb paling lambat Jumat"), Ringkas menghitung tanggal pastinya dan menjadwalkan pengingat otomatis — satu hari sebelumnya dan di hari-H, pagi hari, lewat WIB.

Kalau di-mention dengan pertanyaan ("kapan bayar iuran study tour?"), Ringkas mencari jawabannya di riwayat pesan grup yang sungguh-sungguh ada, lalu menjawab sambil menyebut sumbernya. Kalau tidak ketemu, Ringkas mengaku jujur — "Aku tidak menemukan info itu di grup" — daripada mengarang jawaban.

Pengguna juga bisa mengaktifkan ringkasan personal lewat DM (`/mulai`), lalu memberi tahu konteks singkat tentang diri mereka (`/konteks anak saya ikut study tour dan pramuka`). Ringkasan yang dikirim ke DM akan menyorot bagian yang paling relevan dengan konteks itu — dua orang tua di grup yang sama bisa menerima ringkasan personal yang berbeda penekanannya.

Satu fitur yang kami anggap paling penting untuk kepercayaan pengguna: koreksi manual. Kalau seseorang bilang ke bot "itu penting ya, tolong diingat", Ringkas menyimpan kata kunci itu dan sejak saat itu pesan yang menyinggungnya tidak akan pernah lagi dianggap noise — perilaku bot benar-benar berubah berdasarkan koreksi pengguna, bukan cuma pura-pura mendengarkan.

## 3. Arsitektur AI Agent

Ringkas dibangun di atas **Hermes Agent** (Nous Research), framework wajib lomba ini. Hermes memegang koneksi bot Telegram sepenuhnya — tidak ada service penerima pesan terpisah. Logika inti (menyimpan pesan, menentukan kapan bot boleh membalas, menjaga persona) diimplementasikan sebagai plugin Hermes yang menyambung ke hook `pre_gateway_dispatch`, titik intersepsi paling awal sebelum Hermes memutuskan apakah sebuah pesan perlu direspons.

Agent punya akses ke tujuh MCP tool kustom: mengambil pesan dalam rentang waktu, mencari pesan lama (full-text search SQLite/FTS5), menyimpan ringkasan dan item terstruktur, membuat tenggat dengan pengingat otomatis, mencatat koreksi kata kunci penting, dan menghapus data grup atas permintaan admin.

Ringkasan harian dan pengingat tenggat sengaja TIDAK dijalankan lewat sesi percakapan agent biasa, melainkan sebagai cron job independen yang memanggil model bahasa secara langsung. Alasannya teknis tapi penting: agent Hermes tidak otomatis tahu tanggal hari ini kecuali diberi tahu lewat tool terminal — cocok untuk percakapan interaktif, tapi berisiko untuk job berjadwal tetap yang perlu tahu "hari ini" yang berbeda setiap kali jalan. Memisahkan jalur ini membuat ringkasan otomatis lebih deterministik dan diuji terpisah dari kualitas jawaban agent saat di-mention.

Seluruh sistem berjalan sebagai systemd service di VPS 4 core / 4GB RAM, diuji tahan reboot server sungguhan tanpa campur tangan manual.

## 4. Privasi & Etika

Data privasi bukan tempelan di proyek ini. Begitu bot pertama kali aktif di sebuah grup, ia mengirim pesan perkenalan yang menjelaskan data apa yang disimpan dan berapa lama. Pesan mentah disimpan sementara (default 7 hari) lalu dihapus otomatis oleh job retensi harian — ringkasan dan item penting yang sudah diekstrak tetap tersimpan, tapi isi obrolan asli tidak menumpuk selamanya.

Admin grup bisa kapan saja mengetik `/hapusdata` untuk menghapus permanen semua data grup itu — pesan, ringkasan, tenggat, pengingat. Perintah ini sengaja diimplementasikan sebagai command langsung, bukan tool yang bisa dipanggil agent secara otonom, supaya penghapusan data tidak pernah bisa terpicu tidak sengaja lewat manipulasi isi pesan grup (prompt injection). Ada juga langkah konfirmasi dua tahap sebelum data benar-benar hilang.

## 5. Hasil & Dampak

Karena bot baru mulai diuji beberapa hari terakhir di grup uji kecil, angka dampak nyata (waktu yang dihemat pengguna sungguhan) masih terbatas skalanya. Yang sudah kami ukur secara formal adalah akurasi penyaring noise: dari 260 pesan simulasi grup orang tua kelas berbahasa Indonesia (21 di antaranya berlabel "penting" secara manual), penyaring noise mencapai **recall 100% dan precision 100%** — setiap pesan penting lolos saring, dan tidak ada pesan noise yang salah dianggap penting.

Angka itu tidak didapat langsung sempurna. Evaluasi pertama menunjukkan recall 95%, precision cuma 31% — banyak variasi ucapan singkat seperti "sipp mantap" atau "wokeh siap" lolos dianggap penting karena tidak persis cocok daftar kata kunci. Temuan dari evaluasi itu sendiri yang memicu dua perbaikan konkret pada aturan penyaringan, sebelum akhirnya mencapai angka sempurna.

## 6. Keterbatasan & Rencana Lanjutan

Karena tekanan waktu submit, dashboard web (statistik, kalender tenggat, pengaturan visual) belum dibangun — sebagai gantinya tersedia perintah `/statistik` langsung di chat. Bot baru diuji di grup Telegram; integrasi WhatsApp — platform yang sebenarnya paling umum dipakai grup keluarga/kelas di Indonesia — jadi target pengembangan berikutnya, meskipun secara teknis lebih berisiko (bot WhatsApp tidak resmi rawan pemblokiran nomor). Evaluasi formal juga baru mengukur penyaring noise berbasis aturan, belum akurasi ekstraksi item terstruktur oleh model bahasa.

## 7. Transparansi Penggunaan AI

Seluruh proyek ini dikembangkan bersama Claude Code (Anthropic) sebagai pair-programming partner, berjalan langsung di VPS produksi. Claude Code menulis hampir seluruh kode (skema database, penyaring noise, plugin Hermes, MCP tools, cron job, unit test, data evaluasi), tapi yang lebih penting: ia diberi mandat untuk memverifikasi setiap asumsi lewat pengujian live di Telegram, bukan cuma menulis kode yang "terlihat benar". Proses itu berulang kali menemukan bug nyata yang tidak akan ketahuan dari sekadar membaca kode — mulai dari deteksi mention yang ternyata tidak pernah berfungsi sejak awal, provider LLM yang salah dikonfigurasi, sampai wildcard allowlist Telegram yang ternyata tidak berfungsi seperti dikira. Setiap keputusan arsitektur dan bug yang ditemukan dicatat lengkap di `docs/DECISIONS.md` proyek ini untuk transparansi penuh.
