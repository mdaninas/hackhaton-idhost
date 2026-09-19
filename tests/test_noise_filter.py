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
