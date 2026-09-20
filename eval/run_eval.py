"""Hitung recall & precision penyaring noise (is_noise) terhadap data seed.

Lingkup evaluasi ini: apakah is_noise() (rule-based, tanpa LLM) benar
membedakan pesan penting vs noise di level PESAN. Ini bukan evaluasi
akurasi ekstraksi item terstruktur oleh LLM (/ringkas) -- itu di luar
cakupan skrip ini, dicatat sebagai keterbatasan di docs/EVAL.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from ringkas.noise_filter import is_noise  # noqa: E402

LABELS_PATH = Path(__file__).resolve().parent / "labels.json"


def main() -> None:
    if not LABELS_PATH.exists():
        print("labels.json belum ada -- jalankan `python eval/seed_group.py` dulu.")
        sys.exit(1)

    data = json.loads(LABELS_PATH.read_text())

    tp = fp = fn = tn = 0
    salah_dianggap_noise = []  # false negative: penting tapi dianggap noise
    salah_dianggap_penting = []  # false positive: noise tapi dianggap penting

    for p in data:
        prediksi_penting = not is_noise(p["teks"], jenis=p["jenis"])
        label_penting = p["label_penting"]

        if label_penting and prediksi_penting:
            tp += 1
        elif label_penting and not prediksi_penting:
            fn += 1
            salah_dianggap_noise.append(p["teks"])
        elif not label_penting and prediksi_penting:
            fp += 1
            salah_dianggap_penting.append(p["teks"])
        else:
            tn += 1

    recall = tp / (tp + fn) if (tp + fn) else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0

    print(f"Total pesan: {len(data)}")
    print(f"Berlabel penting: {tp + fn}, berlabel noise: {fp + tn}")
    print(f"Recall: {recall:.1%}  ({tp}/{tp + fn} pesan penting terdeteksi)")
    print(f"Precision: {precision:.1%}  ({tp}/{tp + fp} yang dianggap penting benar-benar penting)")
    if salah_dianggap_noise:
        print("\nPenting tapi salah dianggap noise (false negative):")
        for t in salah_dianggap_noise:
            print(f"  - {t!r}")
    if salah_dianggap_penting:
        print("\nNoise tapi salah dianggap penting (false positive):")
        for t in salah_dianggap_penting:
            print(f"  - {t!r}")

    return {
        "total": len(data),
        "recall": recall,
        "precision": precision,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "false_negative_examples": salah_dianggap_noise,
        "false_positive_examples": salah_dianggap_penting,
    }


if __name__ == "__main__":
    main()
