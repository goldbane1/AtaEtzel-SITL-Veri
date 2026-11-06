# -*- coding: utf-8 -*-
"""Kanal bozulması için SITL gerektirmeyen testler."""

import statistics
import sys
from pathlib import Path

import pytest
import yaml

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "betikler"))

from pymavlink.dialects.v20 import ardupilotmega as mavlink2  # noqa: E402

import kayit_proxy  # noqa: E402
from kanal import Kanal, KanalAyari, ayar_olustur  # noqa: E402

G, U = "gcs2uav", "uav2gcs"
PROFILLER = yaml.safe_load((KOK / "config.yaml").read_text(encoding="utf-8"))["kanal_profilleri"]


class SahteSaat:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _kanal(gecikme=0.0, jitter=0.0, kayip=0.0, tohum=1):
    saat = SahteSaat()
    return Kanal(KanalAyari("test", gecikme, jitter, kayip, tohum), saat), saat


@pytest.mark.parametrize("ad,gecikme,jitter,kayip", [
    ("hafif", 20, 5, 1), ("orta", 80, 20, 3), ("agir", 200, 60, 8),
])
def test_profil_degerleri_yol_haritasiyla_ayni(ad, gecikme, jitter, kayip):
    p = PROFILLER[ad]
    assert (p["gecikme_ms"], p["jitter_ms"], p["kayip_yuzde"]) == (gecikme, jitter, kayip)


@pytest.mark.parametrize("ad", ["hafif", "orta", "agir"])
@pytest.mark.parametrize("yon", [G, U])
def test_olculen_gecikme_ve_kayip_profille_uyumlu(ad, yon):
    ayar = ayar_olustur({"kanal_profilleri": PROFILLER}, ad, 7)
    saat = SahteSaat()
    k = Kanal(ayar, saat)
    for _ in range(20000):
        k.gonder(yon, lambda: None)
        saat.t += 1.0                       # paketler birbirini etkilemesin
        k.zamani_gelenleri_gonder()
    k.bosalt()
    olculen = k.ozet()["olculen"][yon]
    assert olculen["olculen_kayip_yuzde"] == pytest.approx(ayar.kayip_yuzde, abs=0.6)
    # Sahte saatte paket bir sonraki turda gider; gecikmeyi seçilen değerden ölçeriz.
    k2 = Kanal(ayar, saat)
    secilen = [k2._gecikme_sec_s(yon) * 1000 for _ in range(20000)]
    assert statistics.fmean(secilen) == pytest.approx(ayar.gecikme_ms, abs=1.5)
    assert min(secilen) >= ayar.gecikme_ms - ayar.jitter_ms
    assert max(secilen) <= ayar.gecikme_ms + ayar.jitter_ms


def test_paket_zamani_gelmeden_gonderilmez():
    k, saat = _kanal(gecikme=100)
    giden = []
    k.gonder(G, lambda: giden.append(1))
    saat.t = 0.05
    k.zamani_gelenleri_gonder()
    assert not giden
    assert k.sonraki_sure_s() == pytest.approx(0.05)
    saat.t = 0.11
    k.zamani_gelenleri_gonder()
    assert giden == [1]
    assert k.sonraki_sure_s() is None
    assert k.ozet()["olculen"][G]["olculen_gecikme_ms"] == pytest.approx(110)


def test_ayni_tohum_ayni_kararlar_farkli_tohum_farkli():
    def kararlar(tohum):
        k, _ = _kanal(kayip=30, tohum=tohum)
        return [k.gonder(U, lambda: None) for _ in range(300)]
    assert kararlar(5) == kararlar(5)
    assert kararlar(5) != kararlar(6)


def test_yonlerin_kararlari_bagimsiz():
    k, _ = _kanal(kayip=30)
    a = [k.gonder(G, lambda: None) for _ in range(300)]
    b = [k.gonder(U, lambda: None) for _ in range(300)]
    assert a != b


def test_ayni_yonde_sira_bozulmaz():
    k, saat = _kanal(gecikme=50, jitter=50)
    giden = []
    for i in range(200):
        k.gonder(G, lambda i=i: giden.append(i))
        saat.t += 0.001
    saat.t += 1
    k.zamani_gelenleri_gonder()
    assert giden == sorted(giden)


def test_kume_ayni_gecikmeyi_alir_kayip_paket_basina():
    k, saat = _kanal(gecikme=100, kayip=50)
    assert k.toplu_gonder(U, [lambda: None] * 100) < 100
    zamanlar = {oge[0] for oge in k._kuyruk}
    assert len(zamanlar) == 1


def test_temiz_kanal_hemen_gonderir():
    k = Kanal()
    giden = []
    assert k.temiz and k.gonder(G, lambda: giden.append(1))
    assert giden == [1]
    assert k.sonraki_sure_s() is None


def test_bilinmeyen_profil_ve_gecersiz_kayip():
    with pytest.raises(ValueError):
        ayar_olustur({"kanal_profilleri": PROFILLER}, "yok")
    with pytest.raises(ValueError):
        ayar_olustur({"kanal_profilleri": PROFILLER}, "orta", kayip_yuzde=120)


def test_komut_satiri_degeri_profili_ezer():
    a = ayar_olustur({"kanal_profilleri": PROFILLER}, "orta", 3, gecikme_ms=10)
    assert (a.gecikme_ms, a.jitter_ms, a.kayip_yuzde, a.tohum) == (10, 20, 3, 3)


def test_ozet_meta_alanlari():
    k, _ = _kanal(gecikme=10, jitter=2, kayip=5, tohum=9)
    o = k.ozet()
    assert (o["profil"], o["tohum"], o["kayip_yuzde"]) == ("test", 9, 5)
    assert set(o["olculen"][G]) == {"gelen", "dusen", "gonderilen", "olculen_kayip_yuzde",
                                    "olculen_gecikme_ms"}


# --- Proxy ile birlikte ---------------------------------------------------
class SahteSoket:
    def __init__(self):
        self.gonderilen = []

    def sendto(self, veri, adres):
        self.gonderilen.append((veri, adres))

    def sendall(self, veri):
        self.gonderilen.append(veri)


def _paket(seq_uretici=None):
    u = seq_uretici or mavlink2.MAVLink(None, 255, 0)
    return u.heartbeat_encode(6, 8, 0, 0, 0).pack(u)


def _proxy(tmp_path, kanal=None):
    proxy = kayit_proxy.KayitProxy("F100_normal", {"veri_klasoru": str(tmp_path)}, kanal)
    proxy.udp_sok, proxy.enjeksiyon_sok, proxy.tcp_sok = SahteSoket(), SahteSoket(), SahteSoket()
    proxy.gcs_adresleri.add(("127.0.0.1", 1))
    return proxy


GCS = ("127.0.0.1", 1)


def test_gcs2uav_kaybolan_paket_kaydedilmez_iletilmez(tmp_path):
    k, _ = _kanal(kayip=100)
    proxy = _proxy(tmp_path, k)
    proxy.gcs_paketi_al(_paket(), GCS)
    k.bosalt()
    assert len(proxy.yazici.kuyruk) == 0
    assert proxy.tcp_sok.gonderilen == []
    assert GCS in proxy.gcs_adresleri  # adres yine de öğrenilir


def test_gcs2uav_kayit_gecikmeden_sonra(tmp_path):
    k, saat = _kanal(gecikme=100)
    proxy = _proxy(tmp_path, k)
    proxy.gcs_paketi_al(_paket(), GCS)
    assert len(proxy.yazici.kuyruk) == 0 and proxy.tcp_sok.gonderilen == []
    saat.t = 0.2
    k.zamani_gelenleri_gonder()
    assert len(proxy.yazici.kuyruk) == 1 and len(proxy.tcp_sok.gonderilen) == 1


def test_uav2gcs_kaybolan_paket_kayitta_durur_iletilmez(tmp_path):
    k, _ = _kanal(kayip=100)
    proxy = _proxy(tmp_path, k)
    proxy.uav_paketi_al(_paket(mavlink2.MAVLink(None, 1, 1)))
    k.bosalt()
    assert len(proxy.yazici.kuyruk) == 1
    assert proxy.udp_sok.gonderilen == []


def test_uav2gcs_kayit_hemen_iletim_gecikmeli(tmp_path):
    k, saat = _kanal(gecikme=100)
    proxy = _proxy(tmp_path, k)
    proxy.uav_paketi_al(_paket(mavlink2.MAVLink(None, 1, 1)))
    assert len(proxy.yazici.kuyruk) == 1 and proxy.udp_sok.gonderilen == []
    saat.t = 0.2
    k.zamani_gelenleri_gonder()
    assert len(proxy.udp_sok.gonderilen) == 1


def test_enjeksiyon_kaybolursa_kaydedilmez_gcsye_gitmez(tmp_path):
    k, _ = _kanal(kayip=100)
    proxy = _proxy(tmp_path, k)
    proxy.enjeksiyonu_isle(_paket(mavlink2.MAVLink(None, 1, 1)), ("127.0.0.1", 2))
    k.bosalt()
    assert len(proxy.yazici.kuyruk) == 0 and proxy.udp_sok.gonderilen == []


def test_temiz_kanalda_baytlar_degismeden_gecer(tmp_path):
    proxy = _proxy(tmp_path)
    veri = b"\x10\x11" + _paket(mavlink2.MAVLink(None, 1, 1)) + b"\x12"
    proxy.uav_paketi_al(veri)
    assert proxy.udp_sok.gonderilen == [(veri, GCS)]


def test_kapanista_kuyruktaki_gcs2uav_paketleri_kaybolmaz(tmp_path):
    k, _ = _kanal(gecikme=1000)
    proxy = _proxy(tmp_path, k)
    proxy.gcs_paketi_al(_paket(), GCS)
    k.bosalt()
    assert len(proxy.yazici.kuyruk) == 1


def test_meta_jsonda_kanal_alani(tmp_path):
    k, _ = _kanal(gecikme=5, tohum=3)
    proxy = _proxy(tmp_path, k)
    proxy.meta_baslat()
    proxy.meta_guncelle_kapanis()
    import json
    meta = json.loads(proxy.meta_yolu.read_text(encoding="utf-8"))
    assert meta["kanal"]["profil"] == "test" and meta["kanal"]["tohum"] == 3

