# -*- coding: utf-8 -*-
"""ucus_yap.py operatör planı ve görev irtifası için SITL'siz testler."""

import statistics
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "betikler"))

import ucus_yap  # noqa: E402
from ucus_yap import OperatorYurutucu, irtifa_uygula, operator_plani  # noqa: E402

SIRALAR = [2, 3, 4, 5]


class Mesaj(SimpleNamespace):
    def __init__(self, tur, **alanlar):
        super().__init__(**alanlar)
        self._tur = tur

    def get_type(self):
        return self._tur


class SahteMav:
    def __init__(self):
        self.gonderilen = []

    def __getattr__(self, ad):
        return lambda *a: self.gonderilen.append((ad, a))


class SahteBaglanti:
    target_system, target_component = 1, 1

    def __init__(self):
        self.mav = SahteMav()
        self.modlar = []

    def mode_mapping(self):
        return {"LOITER": 12, "AUTO": 10}

    def set_mode(self, mod):
        self.modlar.append(mod)


def test_ayni_tohum_ayni_plan():
    assert operator_plani(42, 35, 300, SIRALAR) == operator_plani(42, 35, 300, SIRALAR)


def test_farkli_tohum_farkli_plan():
    assert operator_plani(42, 35, 300, SIRALAR) != operator_plani(43, 35, 300, SIRALAR)


@pytest.mark.parametrize("tohum", range(25))
def test_son_bosluga_ve_kalkis_oncesine_komut_konmaz(tohum):
    plan = operator_plani(tohum, 35, 280, SIRALAR)
    assert plan
    assert all(35 < adim["t_s"] < 280 for adim in plan)


def test_komut_araliklarinin_ortalamasi_20_40():
    aralar = []
    for tohum in range(40):
        ana = [a["t_s"] for a in operator_plani(tohum, 0, 600, SIRALAR) if a["tur"] == "ana"]
        aralar += [b - a for a, b in zip(ana, ana[1:])]
    assert all(20 <= x <= 40 for x in aralar)
    assert 28 < statistics.mean(aralar) < 32


def test_her_islem_turu_gorulur_ve_durum_sorgusu_vardir():
    adimlar = [a for t in range(30) for a in operator_plani(t, 0, 300, SIRALAR)]
    assert {"mod", "hiz_degistir", "param_oku", "gorev_sirasi", "mesaj_hizi",
            "durum_sorgusu"} == {a["komut"] for a in adimlar}


def test_loiterdan_her_zaman_autoya_donulur():
    for tohum in range(30):
        plan = operator_plani(tohum, 0, 300, SIRALAR)
        modlar = [a for a in plan if a["komut"] == "mod"]
        assert len(modlar) % 2 == 0
        for git, don in zip(modlar[::2], modlar[1::2]):
            assert (git["parametre"], don["parametre"]) == ("LOITER", "AUTO")
            assert don["t_s"] < 300


def test_mod_dongusu_sirasinda_baska_gorev_komutu_yok():
    for tohum in range(30):
        plan = [a for a in operator_plani(tohum, 0, 300, SIRALAR) if a["tur"] != "durum"]
        for onceki, sonraki in zip(plan, plan[1:]):
            if onceki["parametre"] == "LOITER":
                assert sonraki["parametre"] == "AUTO"


def test_gorev_sirasi_guvenli_noktalara_gider():
    for tohum in range(30):
        for a in operator_plani(tohum, 0, 300, SIRALAR):
            if a["komut"] == "gorev_sirasi":
                assert a["parametre"] in SIRALAR


def test_gorev_noktasi_yoksa_gorev_sirasi_uretilmez():
    plan = [a for t in range(20) for a in operator_plani(t, 0, 300, [])]
    assert "gorev_sirasi" not in {a["komut"] for a in plan}


@pytest.mark.parametrize("dosya", sorted((KOK / "gorevler").glob("*.waypoints")))
def test_gorev_siralari_kalkis_ve_inisi_icermez(dosya):
    satirlar = [s.split("\t") for s in dosya.read_text(encoding="utf-8").splitlines()[1:]]
    komutlar = {int(s[0]): int(s[3]) for s in satirlar}
    siralar = ucus_yap.gorev_siralari(dosya)
    assert siralar
    assert all(komutlar[s] in (16, 18, 19) for s in siralar)


@pytest.mark.parametrize("dosya", sorted((KOK / "gorevler").glob("*.waypoints")))
def test_gorev_dosyasi_duzgun_ve_tekrar_iceriyor(dosya):
    satirlar = [s.split("\t") for s in dosya.read_text(encoding="utf-8").splitlines()[1:]]
    assert [int(s[0]) for s in satirlar] == list(range(len(satirlar)))
    assert all(len(s) == 12 for s in satirlar)
    assert int(satirlar[-2][3]) == 177            # DO_JUMP
    assert int(float(satirlar[-2][4])) == 2       # ilk görev noktasına döner
    assert int(satirlar[-1][3]) in (20, 21)       # RTL veya LAND


@pytest.mark.skipif(not (Path.home() / "ardupilot").exists(), reason="ArduPilot kaynağı yok")
@pytest.mark.parametrize("ad", ucus_yap.OKUNACAK_PARAMLAR)
def test_okunan_parametre_arduplanede_vardir(ad):
    """Olmayan parametreye uçak yanıt vermez; normal veriye yanıtsız istek girer."""
    kaynak = Path.home() / "ardupilot" / "ArduPlane" / "Parameters.cpp"
    assert f'"{ad}"' in kaynak.read_text(encoding="utf-8")


def test_irtifa_gorev_noktasina_uygulanir():
    assert irtifa_uygula(2, 16, 3, 100.0, 30.0) == 130.0
    assert irtifa_uygula(1, 22, 3, 100.0, -20.0) == 80.0


def test_irtifa_ev_ve_inise_uygulanmaz():
    assert irtifa_uygula(0, 16, 0, 584.0, 30.0) == 584.0
    assert irtifa_uygula(6, 21, 3, 0.0, 30.0) == 0.0
    assert irtifa_uygula(6, 20, 3, 0.0, 30.0) == 0.0
    assert irtifa_uygula(6, 177, 2, 0.0, 30.0) == 0.0


def test_irtifa_kalkis_esiginin_altina_inmez():
    assert irtifa_uygula(2, 16, 3, 100.0, -80.0) == 60.0


def test_yurutucu_zamani_gelince_gonderir_ve_ack_kaydeder():
    baglanti = SahteBaglanti()
    y = OperatorYurutucu(baglanti, [
        {"t_s": 5, "komut": "hiz_degistir", "parametre": 22.0, "tur": "ana"},
        {"t_s": 9, "komut": "param_oku", "parametre": "WP_RADIUS", "tur": "ana"},
    ])
    y.zamani_gelenleri_gonder(4)
    assert not y.kayitlar
    y.zamani_gelenleri_gonder(5)
    assert len(y.kayitlar) == 1
    y.mesaj_isle(Mesaj("COMMAND_ACK", command=178, result=0))
    assert y.kayitlar[0]["ack"] == 0

    y.zamani_gelenleri_gonder(9)
    y.mesaj_isle(Mesaj("PARAM_VALUE", param_id="WP_RADIUS"))
    assert y.kayitlar[1]["ack"] == "param_value"
    assert set(y.kayitlar[0]) == {"t_ns", "komut", "parametre", "ack"}


def test_yurutucu_baska_komutun_acki_ile_eslesmez():
    y = OperatorYurutucu(SahteBaglanti(), [])
    y.gonder({"komut": "hiz_degistir", "parametre": 20.0})
    y.mesaj_isle(Mesaj("COMMAND_ACK", command=400, result=0))
    assert y.kayitlar[0]["ack"] is None


def test_yurutucu_mod_ve_gorev_sirasi():
    baglanti = SahteBaglanti()
    y = OperatorYurutucu(baglanti, [])
    y.gonder({"komut": "mod", "parametre": "LOITER"})
    y.gonder({"komut": "gorev_sirasi", "parametre": 3})
    assert baglanti.modlar == [12]
    y.mesaj_isle(Mesaj("COMMAND_ACK", command=176, result=0))
    y.mesaj_isle(Mesaj("MISSION_CURRENT", seq=2))
    assert y.kayitlar[1]["ack"] is None
    y.mesaj_isle(Mesaj("MISSION_CURRENT", seq=3))
    assert [k["ack"] for k in y.kayitlar] == [0, "mission_current"]


def test_yanitsiz_komutun_ack_alani_dolar():
    y = OperatorYurutucu(SahteBaglanti(), [])
    y.gonder({"komut": "durum_sorgusu", "parametre": 148})
    y.zaman_asimlarini_isle(hepsi=True)
    assert y.kayitlar[0]["ack"] == "zaman_asimi"
    assert not y.bekleyenler
