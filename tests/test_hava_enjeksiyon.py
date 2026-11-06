# -*- coding: utf-8 -*-
"""Havadan enjeksiyon (sahte telemetri) için SITL gerektirmeyen testler."""

import importlib.util
import math
import socket
import sys
from pathlib import Path

import pandas as pd
import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "betikler"))
sys.path.insert(0, str(KOK / "betikler" / "saldirilar"))

from pymavlink.dialects.v20 import ardupilotmega as mavlink2  # noqa: E402

import dogrula  # noqa: E402
import etiketle  # noqa: E402
import kayit_proxy  # noqa: E402
import ortak  # noqa: E402
import saldiri_temel  # noqa: E402

GCS = ("127.0.0.1", 40001)
SALDIRGAN = ("127.0.0.1", 40002)


def _modul():
    yol = KOK / "betikler" / "saldirilar" / "fake_telemetry.py"
    tanim = importlib.util.spec_from_file_location("fake_telemetry", yol)
    modul = importlib.util.module_from_spec(tanim)
    tanim.loader.exec_module(modul)
    return modul


class SahteSoket:
    def __init__(self):
        self.gonderilen = []

    def sendto(self, veri, adres):
        self.gonderilen.append((veri, adres))

    def sendall(self, veri):
        self.gonderilen.append((veri, "SITL"))


def _proxy(tmp_path):
    proxy = kayit_proxy.KayitProxy("F100_fake_telemetry", {"veri_klasoru": str(tmp_path)})
    proxy.udp_sok, proxy.enjeksiyon_sok, proxy.tcp_sok = SahteSoket(), SahteSoket(), SahteSoket()
    proxy.gcs_adresleri.add(GCS)
    return proxy


def _sahte_paket():
    uretici = mavlink2.MAVLink(None, 1, 1)
    return uretici.global_position_int_encode(1, 2, 3, 4, 5, 0, 0, 0, 0).pack(uretici)


def test_enjeksiyon_gcsye_gider_sitlye_gitmez_ve_gcs2uav_kaydedilir(tmp_path):
    proxy = _proxy(tmp_path)
    ham = _sahte_paket()
    proxy.enjeksiyonu_isle(ham, SALDIRGAN)

    assert proxy.udp_sok.gonderilen == [(ham, GCS)]
    assert proxy.tcp_sok.gonderilen == []
    satir = proxy.tampon[0]
    assert satir["direction"] == "gcs2uav"
    assert (satir["src_ip"], satir["src_port"]) == SALDIRGAN
    assert satir["sysid"] == 1
    assert satir["msgname"] == "GLOBAL_POSITION_INT"


def test_enjeksiyon_etiketlemede_fake_telemetry_olur(tmp_path):
    cfg = {"veri_klasoru": str(tmp_path)}
    proxy = _proxy(tmp_path)
    proxy.enjeksiyonu_isle(_sahte_paket(), SALDIRGAN)
    proxy.tamponu_yaz()
    ortak.ground_truth_ekle("F100_fake_telemetry", {
        "attack_type": "fake_telemetry", "start_ns": 0, "end_ns": ortak.simdi_ns(),
        "attacker_addr": f"{SALDIRGAN[0]}:{SALDIRGAN[1]}", "params": {},
    }, cfg)

    assert etiketle.bir_ucus_etiketle("F100_fake_telemetry", cfg)

    yol = ortak.ucus_klasoru("F100_fake_telemetry", cfg) / "paketler.parquet"
    assert pd.read_parquet(yol)["label"].tolist() == ["fake_telemetry"]


def test_enjeksiyon_ayri_ayristirici_kullanir(tmp_path):
    proxy = _proxy(tmp_path)
    assert proxy._mav_enjeksiyon is not proxy._mav_uav
    assert proxy._mav_enjeksiyon is not proxy._mav_gcs
    assert proxy._mav_enjeksiyon.robust_parsing


def test_enjekte_eden_adres_telemetri_kopyasi_alir_kayit_olusmaz(tmp_path):
    proxy = _proxy(tmp_path)
    proxy.enjeksiyonu_isle(_sahte_paket(), SALDIRGAN)
    kayit_sayisi = len(proxy.tampon)
    proxy._dinleyenlere_gonder(b"telemetri")
    assert proxy.enjeksiyon_sok.gonderilen == [(b"telemetri", SALDIRGAN)]
    assert len(proxy.tampon) == kayit_sayisi


def test_gercek_soketle_enjeksiyon_portu_yalnizca_localhosta_acilir(tmp_path):
    cfg = {"veri_klasoru": str(tmp_path), "udp_port": 0, "hava_enjeksiyon_port": 0}
    proxy = kayit_proxy.KayitProxy("F100_fake_telemetry", cfg)
    dinleyici = socket.socket()
    dinleyici.bind(("127.0.0.1", 0))
    dinleyici.listen(1)
    proxy.tcp_port = dinleyici.getsockname()[1]
    try:
        proxy.soketleri_ac()
        assert proxy.enjeksiyon_sok.getsockname()[0] == "127.0.0.1"
    finally:
        for s in (proxy.udp_sok, proxy.enjeksiyon_sok, proxy.tcp_sok, dinleyici):
            if s:
                s.close()


def test_localhost_disi_host_reddedilir(tmp_path):
    proxy = kayit_proxy.KayitProxy("F100_fake_telemetry",
                                   {"veri_klasoru": str(tmp_path), "host": "8.8.8.8"})
    with pytest.raises(SystemExit):
        proxy.soketleri_ac()


def test_saldiri_gondericisi_localhost_disini_reddeder():
    with pytest.raises(SystemExit):
        saldiri_temel.gonderen_kur({"host": "8.8.8.8"}, port=14551)


def test_ortak_localhost_kontrolu_duruyor():
    assert ortak.localhost_mu("127.0.0.1") and not ortak.localhost_mu("8.8.8.8")


@pytest.mark.parametrize("sapma", [50.0, 500.0, 2000.0])
def test_sahte_konum_verilen_uzaklikta(sapma):
    lat, lon = -353632610, 1491652300
    y_lat, y_lon = _modul().sahte_konum(lat, lon, sapma)
    d_lat = (y_lat - lat) / 1e7 * 111_320.0
    d_lon = (y_lon - lon) / 1e7 * 111_320.0 * math.cos(math.radians(lat / 1e7))
    assert math.hypot(d_lat, d_lon) == pytest.approx(sapma, rel=0.01)


def _paketler(yon="gcs2uav", sysid=1):
    return pd.DataFrame([
        {"direction": "uav2gcs", "msgname": "HEARTBEAT", "sysid": 1, "label": "normal"},
        {"direction": yon, "msgname": "GLOBAL_POSITION_INT", "sysid": sysid,
         "label": "fake_telemetry"},
    ])


def test_dogrula_dogru_kaydi_kabul_eder():
    assert dogrula.fake_telemetry_sorunlari(_paketler()) == []


def test_dogrula_yanlis_yonu_yakalar():
    assert any("gcs2uav" in s for s in dogrula.fake_telemetry_sorunlari(_paketler("uav2gcs")))


def test_dogrula_yanlis_sysidi_yakalar():
    assert any("sysid" in s for s in dogrula.fake_telemetry_sorunlari(_paketler(sysid=200)))


def test_diger_ucuslarda_kontrol_devre_disi():
    df = pd.DataFrame([{"direction": "uav2gcs", "msgname": "HEARTBEAT", "sysid": 1,
                        "label": "normal"}])
    assert dogrula.fake_telemetry_sorunlari(df) == []
