# -*- coding: utf-8 -*-
"""ucus_yap.py kalkış doğrulaması için SITL gerektirmeyen testler."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "betikler"))

import ortak  # noqa: E402
import ucus_yap  # noqa: E402
from ucus_yap import ARMED_BAYRAGI, MAV_TYPE_GCS, PLANE_AUTO_MODU, KalkisIzleyici  # noqa: E402


class Mesaj(SimpleNamespace):
    def __init__(self, tur, **alanlar):
        super().__init__(**alanlar)
        self._tur = tur

    def get_type(self):
        return self._tur


def hb(armed=True, mod=PLANE_AUTO_MODU, tip=1):
    return Mesaj("HEARTBEAT", type=tip, base_mode=ARMED_BAYRAGI if armed else 0,
                 custom_mode=mod)


def konum(irtifa_m):
    return Mesaj("GLOBAL_POSITION_INT", relative_alt=int(irtifa_m * 1000))


def gorev(sira):
    return Mesaj("MISSION_CURRENT", seq=sira)


def isle(izleyici, *mesajlar):
    for m in mesajlar:
        izleyici.mesaj_isle(m)
    return izleyici


def test_basarili_kalkis():
    iz = isle(KalkisIzleyici(), hb(), gorev(1), konum(60), gorev(2))
    assert iz.dogrulandi
    assert iz.neden() is None
    assert iz.sonuc()["maks_irtifa_m"] == 60.0


def test_arm_yoksa_basarisiz():
    iz = isle(KalkisIzleyici(), hb(armed=False), konum(0))
    assert not iz.dogrulandi
    assert iz.neden() == "uçak arm olmadı"


def test_auto_yoksa_basarisiz():
    iz = isle(KalkisIzleyici(), hb(mod=0), konum(80), gorev(1), gorev(2))
    assert iz.neden() == "uçak AUTO moduna geçmedi"
    assert not iz.waypoint_ilerlemesi


def test_irtifa_esigi_tam_50_yetmez():
    iz = isle(KalkisIzleyici(), hb(), gorev(1), konum(50), gorev(2))
    assert not iz.dogrulandi
    assert "50 m" in iz.neden()


def test_waypoint_ilerlemesi_yoksa_basarisiz():
    iz = isle(KalkisIzleyici(), hb(), gorev(1), konum(120), gorev(1))
    assert not iz.dogrulandi
    assert iz.neden() == "AUTO modunda waypoint ilerlemesi görülmedi"


def test_kalkis_ogesine_gecis_ilerleme_sayilmaz():
    iz = isle(KalkisIzleyici(), hb(), gorev(0), gorev(1), konum(120))
    assert not iz.waypoint_ilerlemesi


def test_onceki_ucustan_kalan_gorev_sirasi_ilerleme_sayilmaz():
    iz = isle(KalkisIzleyici(), hb(), gorev(6), gorev(1), konum(120))
    assert not iz.waypoint_ilerlemesi
    isle(iz, gorev(2))
    assert iz.dogrulandi


def test_item_reached_ilerleme_sayilir():
    iz = isle(KalkisIzleyici(), hb(), konum(70),
              Mesaj("MISSION_ITEM_REACHED", seq=2))
    assert iz.dogrulandi


def test_gcs_heartbeat_yok_sayilir():
    iz = isle(KalkisIzleyici(), hb(tip=MAV_TYPE_GCS))
    assert not iz.armed_goruldu


def test_dogrulama_sonradan_disarm_ile_bozulmaz():
    iz = isle(KalkisIzleyici(), hb(), gorev(1), konum(60), gorev(2),
              hb(armed=False, mod=0), konum(0))
    assert iz.dogrulandi


def _cfg(tmp_path):
    return {"veri_klasoru": str(tmp_path)}


def test_basarisiz_ucus_meta_jsona_yazilir(tmp_path):
    cfg = _cfg(tmp_path)
    klasor = ortak.ucus_klasoru("F100_normal", cfg)
    klasor.mkdir(parents=True)
    (klasor / "meta.json").write_text(json.dumps({"pc_id": "pc1"}), encoding="utf-8")

    iz = isle(KalkisIzleyici(), hb(armed=False))
    ucus_yap.ucus_sonucu_yaz("F100_normal", cfg, iz.sonuc(), iz.neden())

    meta = json.loads((klasor / "meta.json").read_text(encoding="utf-8"))
    assert meta["ucus_basarili"] is False
    assert meta["basarisizlik_nedeni"] == "uçak arm olmadı"
    assert meta["kalkis_kontrolu"]["dogrulandi"] is False
    assert meta["pc_id"] == "pc1"  # mevcut alanlar korunur


def test_basarili_ucus_meta_jsona_yazilir(tmp_path):
    cfg = _cfg(tmp_path)
    iz = isle(KalkisIzleyici(), hb(), gorev(1), konum(60), gorev(2))
    ucus_yap.ucus_sonucu_yaz("F101_normal", cfg, iz.sonuc(), None)

    meta = json.loads(
        (ortak.ucus_klasoru("F101_normal", cfg) / "meta.json").read_text(encoding="utf-8")
    )
    assert meta["ucus_basarili"] is True
    assert meta["basarisizlik_nedeni"] is None


def test_donma_uyku_olarak_algilanir():
    assert ucus_yap.donma_var_mi(100.0, 106.0)
    assert not ucus_yap.donma_var_mi(100.0, 101.2)
