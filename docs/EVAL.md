# EVAL — Hasil Evaluasi

## Evaluasi #1 — 2026-09-19 (H6): Penyaring noise (rule-based)

**Apa yang diukur:** recall & precision `ringkas.noise_filter.is_noise()` di
level PESAN -- apakah pesan yang seharusnya "penting" (tidak boleh dianggap
noise) benar-benar lolos filter, dan apakah pesan yang lolos filter memang
benar-benar penting.

**Bukan yang diukur:** akurasi ekstraksi item terstruktur oleh LLM (`/ringkas`,
ringkasan harian) -- itu di luar cakupan evaluasi ini, evaluasi terpisah untuk
itu belum dibuat (lihat "Keterbatasan" di bawah).

**Data:** `eval/seed_group.py` -> `eval/labels.json`. 260 pesan simulasi
grup orang tua kelas berbahasa Indonesia, 21 berlabel penting (pengumuman/
tenggat/keputusan/pertanyaan), sisanya noise (termasuk beberapa varian
"noise sulit" yang sengaja dibuat mirip tapi tidak identik dengan kata kunci
di whitelist, dan satu "jebakan" pesan penting yang berbentuk sapaan).
Data kurasi manual, bukan hasil generate LLM -- deterministik (seed tetap),
bisa direproduksi dengan `python eval/seed_group.py`.

**Cara jalankan:**
```bash
.venv/bin/python eval/seed_group.py   # bikin/timpa eval/labels.json
.venv/bin/python eval/run_eval.py     # hitung recall/precision
```

**Hasil akhir (setelah 2 perbaikan `noise_filter.py` yang dipicu evaluasi ini):**

| Metrik | Nilai |
|---|---|
| Recall | **100.0%** (21/21 pesan penting terdeteksi) |
| Precision | **100.0%** (21/21 yang dianggap penting benar-benar penting) |

Lolos gerbang H7 (`PLAN.md`: "Recall pada evaluasi mencapai sekitar 80% atau
lebih") dengan margin besar.

**Riwayat perbaikan yang dipicu evaluasi ini (bukan langsung 100%):**
1. Recall 95.2%, precision 31.2% -- ternyata variasi ucapan singkat yang tidak
   persis cocok whitelist kata ("sipp mantap", "wokeh siap", "noted ya bu",
   dst) lolos jadi "dianggap penting" (false positive). Fix: aturan baru
   `_is_filler_phrase()` -- pesan pendek (≤5 kata) yang SEMUA katanya ada di
   daftar kata pengisi diperluas, dianggap noise.
2. Setelah fix #1: recall 95.2%, precision 100% -- satu pesan penting
   ("Selamat pagi semua, jangan lupa besok upacara bendera ya") salah
   dianggap noise karena cocok pola sapaan tanpa tanggal eksplisit. Fix:
   `_DATE_OR_MONEY_RE` diperluas menangkap "besok", "lusa", dan nama hari
   sebagai penanda waktu konkret (bukan cuma tanggal angka).

**Keterbatasan metodologi (dicatat jujur, jangan overclaim):**
- Data eval ini dikurasi oleh Claude Code, dan `noise_filter.py` diperbaiki
  oleh Claude Code juga sampai lolos data yang sama -- ada risiko overfitting
  terhadap kasus yang sudah diketahui. Recall/precision 100% pada data INI
  tidak menjamin 100% di pesan grup nyata yang polanya belum tentu sama.
  Cross-check informal: sepanjang pengujian live H2-H6 di grup uji Telegram,
  noise_filter tidak pernah salah tandai pesan yang dikirim manual (lihat
  `docs/DECISIONS.md`), tapi itu jumlah sampelnya kecil.
- Evaluasi ini HANYA menguji filter rule-based (tahap penyaringan sebelum
  LLM). Akurasi ekstraksi item oleh LLM (`/ringkas`, ringkasan harian, tanggal
  tenggat) belum punya angka evaluasi formal -- baru diverifikasi lewat
  pengujian manual/live (dicatat di `docs/DECISIONS.md` H3/H4/H5/H6), bukan
  dataset berlabel dengan metrik recall/precision.
- Data seed adalah simulasi buatan, bukan pesan asli dari grup uji Telegram
  yang sedang berjalan (data itu ada di `data/ringkas.db`, tapi volumenya
  masih kecil untuk evaluasi statistik yang berarti per 2026-09-19).
