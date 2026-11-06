# -*- coding: utf-8 -*-
"""bol.py değerlendirme bölmeleri için SITL'siz testler."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "betikler"))

import bol  # noqa: E402

TURLER = ("normal", "spoof_cmd", "impersonation", "replay", "flood", "fake_telemetry")
PROFILLER = ("temiz", "hafif", "orta", "agir")


def _ucuslar(adet=10):
    no = 100
    ucuslar = {}
    for tur in TURLER:
        for profil in PROFILLER:
            for _ in range(adet):
                ucuslar[f"F{no}_{tur}"] = (tur, profil)
                no += 1
    return ucuslar


def _hazir(adet=10, tohum=42):
    ucuslar = _ucuslar(adet)
    atama = bol.katmanli_bol(ucuslar, 0.6, 0.2, tohum)
    return ucuslar, atama, bol.senaryo_bolmeleri(atama, ucuslar)


def test_ana_bolme_oranlari_ve_tum_ucuslar():
    ucuslar, atama, _ = _hazir()
    assert set(atama) == set(ucuslar)
    kumeler = list(atama.values())
    assert kumeler.count("egitim") / len(kumeler) == pytest.approx(0.6, abs=0.02)
    assert kumeler.count("dogrulama") / len(kumeler) == pytest.approx(0.2, abs=0.02)


def test_her_katman_her_kumede():
    ucuslar, atama, _ = _hazir()
    for katman in set(ucuslar.values()):
        kumeler = {atama[u] for u, k in ucuslar.items() if k == katman}
        assert kumeler == {"egitim", "dogrulama", "test"}


def test_ayni_tohum_ayni_bolme_farkli_tohum_farkli():
    assert _hazir(tohum=1)[1] == _hazir(tohum=1)[1]
    assert _hazir(tohum=1)[1] != _hazir(tohum=2)[1]


def test_senaryo_adlari():
    _, _, s = _hazir()
    assert set(s) == {"T1", "T2", "T3", *(f"T4_{t}" for t in TURLER[1:])}


def _kume(senaryo, kume):
    return {u for u, k in senaryo.items() if k == kume}


def test_t1_testi_yalnizca_temiz():
    ucuslar, _, s = _hazir()
    assert {ucuslar[u][1] for u in _kume(s["T1"], "test")} == {"temiz"}


def test_t2_testi_egitimde_gorulen_bozulma():
    ucuslar, _, s = _hazir()
    assert {ucuslar[u][1] for u in _kume(s["T2"], "test")} == {"hafif", "orta"}


def test_t3_agir_egitim_ve_dogrulamada_yok_testte_var():
    ucuslar, _, s = _hazir()
    assert all(ucuslar[u][1] != "agir" for u in _kume(s["T3"], "egitim") | _kume(s["T3"], "dogrulama"))
    assert _kume(s["T3"], "test") == {u for u, k in ucuslar.items() if k[1] == "agir"}


@pytest.mark.parametrize("tur", TURLER[1:])
def test_t4_cikarilan_tur_egitimde_yok_testte_var(tur):
    ucuslar, _, s = _hazir()
    sen = s[f"T4_{tur}"]
    egitim = _kume(sen, "egitim") | _kume(sen, "dogrulama")
    assert all(ucuslar[u][0] != tur for u in egitim)
    assert {u for u, k in ucuslar.items() if k[0] == tur} <= _kume(sen, "test")
    assert len({ucuslar[u][0] for u in egitim}) == len(TURLER) - 1


def test_hicbir_dosyada_egitim_araliginda_agir_yok():
    ucuslar, _, s = _hazir()
    for senaryo in s.values():
        for u, k in senaryo.items():
            if k != "test":
                assert ucuslar[u][1] != "agir"


def test_yetersiz_ucusta_turkce_uyari(capsys):
    ucuslar = {"F100_normal": ("normal", "temiz")}
    atama = bol.katmanli_bol(ucuslar, 0.6, 0.2, 1)
    bol.senaryo_uyarilari(bol.senaryo_bolmeleri(atama, ucuslar))
    cikti = capsys.readouterr().out
    assert "katmanlama zayıf" in cikti
    assert "test kümesi boş" in cikti


def test_csv_yazimi_tek_kume(tmp_path):
    yol = tmp_path / "a" / "T1.csv"
    bol._csv_yaz(yol, {"F2_x": "test", "F1_y": "egitim"})
    assert yol.read_text(encoding="utf-8").splitlines() == [
        "flight_id,split", "F1_y,egitim", "F2_x,test"]
