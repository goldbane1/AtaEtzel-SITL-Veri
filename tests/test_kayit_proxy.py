# -*- coding: utf-8 -*-
"""kayit_proxy.py ayrıştırma davranışı için SITL gerektirmeyen testler."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "betikler"))

from pymavlink.dialects.v20 import ardupilotmega as mavlink2  # noqa: E402

import kayit_proxy  # noqa: E402


def _proxy(tmp_path):
    return kayit_proxy.KayitProxy("F100_normal", {"veri_klasoru": str(tmp_path)})


def _heartbeat():
    gonderici = mavlink2.MAVLink(None, 1, 1)
    return gonderici.heartbeat_encode(1, 3, 0, 0, 0).pack(gonderici)


def test_akis_basindaki_coplukten_sonra_mesajlar_aninda_cozulur(tmp_path):
    """SITL bağlantı başında MAVLink olmayan bayt yollar.

    Hata: Ayrıştırıcı burada takılıp saniyelerce mesaj çıkarmıyor, sonra hepsini
    birden veriyordu; paketler yanlış zamanla damgalanıyordu. Her mesaj,
    geldiği parçada çözülmelidir.
    """
    proxy = _proxy(tmp_path)
    proxy._paketleri_coz(proxy._mav_uav, b"\x10" * 64 + _heartbeat(), "uav2gcs", "127.0.0.1", 5760)
    assert len(proxy.yazici.kuyruk) == 1

    for beklenen in range(2, 6):
        proxy._paketleri_coz(proxy._mav_uav, _heartbeat(), "uav2gcs", "127.0.0.1", 5760)
        assert len(proxy.yazici.kuyruk) == beklenen


def test_parcalanmis_mesaj_tamamlaninca_cozulur(tmp_path):
    proxy = _proxy(tmp_path)
    ham = _heartbeat()
    proxy._paketleri_coz(proxy._mav_uav, ham[:5], "uav2gcs", "127.0.0.1", 5760)
    assert len(proxy.yazici.kuyruk) == 0
    proxy._paketleri_coz(proxy._mav_uav, ham[5:], "uav2gcs", "127.0.0.1", 5760)
    assert len(proxy.yazici.kuyruk) == 1


def test_iki_yonun_ayristiricisi_saglam_modda(tmp_path):
    proxy = _proxy(tmp_path)
    assert proxy._mav_gcs.robust_parsing and proxy._mav_uav.robust_parsing
