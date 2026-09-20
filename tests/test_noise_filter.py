from ringkas.noise_filter import is_noise


def test_stiker_tanpa_teks_adalah_noise():
    assert is_noise("", jenis="sticker") is True


def test_gif_tanpa_teks_adalah_noise():
    assert is_noise("", jenis="gif") is True


def test_stiker_dengan_caption_bukan_noise():
    assert is_noise("jangan lupa besok kumpul jam 8", jenis="sticker") is False


def test_emoji_saja_adalah_noise():
    assert is_noise("👍") is True
    assert is_noise("😂😂😂") is True
    assert is_noise("🔥🔥") is True


def test_pesan_pendek_standar_adalah_noise():
    for teks in ["ok", "Ok", "siap", "SIAP!", "noted", "aamiin", "makasih", "wkwk", "wkwkwk", "sip"]:
        assert is_noise(teks) is True, f"'{teks}' harusnya noise"


def test_ucapan_standar_tanpa_tanggal_adalah_noise():
    assert is_noise("Selamat ulang tahun ya!") is True
    assert is_noise("Met ultah semoga sehat selalu") is True
    assert is_noise("Selamat pagi semuanya") is True


def test_ucapan_dengan_tanggal_bukan_noise():
    assert is_noise("Selamat ulang tahun, jangan lupa acara tanggal 5/10 ya") is False


def test_ucapan_dengan_nominal_uang_bukan_noise():
    assert is_noise("Selamat atas kelahirannya, kado patungan Rp 50.000 per orang ya") is False


def test_pesan_biasa_bukan_noise():
    assert is_noise("Besok jam berapa kumpulnya?") is False
    assert is_noise("Iuran study tour 250rb paling lambat Jumat") is False
    assert is_noise("Menurut saya sebaiknya kita pilih opsi B karena lebih murah") is False


def test_pesan_kosong_non_text_default_noise():
    assert is_noise("", jenis="photo") is True


def test_pesan_kosong_text_bukan_noise_khusus():
    # Teks kosong tapi jenis text (kasus jarang) -> dianggap bukan target noise stiker/gif.
    assert is_noise("", jenis="text") is False


def test_kata_kunci_penting_override_noise():
    # "ok" normalnya noise, tapi kalau menyinggung kata kunci hasil koreksi -> bukan noise.
    assert is_noise("ok", kata_kunci_penting=["iuran"]) is True
    assert is_noise("ok soal iuran ya", kata_kunci_penting=["iuran"]) is False


def test_kata_kunci_penting_case_insensitive():
    assert is_noise("🙏", kata_kunci_penting=["IURAN"]) is True
    assert is_noise("makasih IURAN nya udah dibayar", kata_kunci_penting=["iuran"]) is False


def test_kata_kunci_penting_kosong_tidak_berefek():
    assert is_noise("ok", kata_kunci_penting=[]) is True
    assert is_noise("ok", kata_kunci_penting=None) is True


def test_frasa_pendek_variasi_kata_pengisi_adalah_noise():
    for teks in ["sipp mantap", "wokeh siap", "noted ya bu", "trims banyak ya", "hehe iya betul"]:
        assert is_noise(teks) is True, f"'{teks}' harusnya noise (H6: eval/run_eval.py)"


def test_frasa_panjang_tidak_disamakan_kata_pengisi():
    # >5 kata -> tidak dianggap frasa pengisi walau semua kata "familiar".
    assert is_noise("ya ya ya ya ya ya ya") is False


def test_ucapan_dengan_penanda_hari_relatif_bukan_noise():
    assert is_noise("Selamat pagi semua, jangan lupa besok upacara bendera ya") is False
    assert is_noise("Selamat pagi, Senin nanti ada acara sekolah") is False
