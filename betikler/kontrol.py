#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kontrol.py — Kurulum sonrası sağlık kontrolü.

Bu betik, bir makinenin veri üretimine hazır olup olmadığını denetler ve
her maddeyi Türkçe TAMAM/HATA olarak raporlar:
  - ArduPlane SITL derlenmiş mi (~/ardupilot/build/sitl/bin/arduplane)
  - pymavlink ve MAVProxy import edilebiliyor mu
  - config.yaml okunabiliyor mu
  - Gerekli portlar boş mu (14550 UDP mantıksal, 5760 TCP)

Kullanım:
    python betikler/kontrol.py
"""

from __future__ import annotations

import argparse
import importlib
import socket
from pathlib import Path

import ortak


def _tamam(mesaj: str) -> bool:
    ortak.log(mesaj, "TAMAM")
    return True


def _hata(mesaj: str) -> bool:
    ortak.log(mesaj, "HATA")
    return False


def arduplane_derlenmis_mi() -> bool:
    """ArduPlane SITL ikilisi oluşmuş mu diye bakar."""
    aday_yollar = [
        Path.home() / "ardupilot" / "build" / "sitl" / "bin" / "arduplane",
        Path.home() / "ardupilot" / "build" / "sitl" / "bin" / "ArduPlane",
    ]
    for yol in aday_yollar:
        if yol.exists():
            return _tamam(f"ArduPlane SITL derlenmiş: {yol}")
    return _hata(
        "ArduPlane SITL ikilisi bulunamadı (~/ardupilot/build/sitl/bin/). "
        "Önce 'bash setup.sh' çalıştırın."
    )


def modul_import_edilebiliyor_mu(ad: str) -> bool:
    """Bir Python modülünün import edilip edilemediğini sınar."""
    try:
        importlib.import_module(ad)
        return _tamam(f"'{ad}' import edilebiliyor.")
    except Exception as e:  # noqa: BLE001
        return _hata(f"'{ad}' import edilemedi: {e}")


def mavproxy_var_mi() -> bool:
    """mavproxy.py komutu PATH'te mi diye bakar."""
    import shutil

    if shutil.which("mavproxy.py"):
        return _tamam("mavproxy.py PATH'te bulundu.")
    # Modül olarak da denenebilir
    try:
        importlib.import_module("MAVProxy")
        return _tamam("MAVProxy modülü import edilebiliyor.")
    except Exception:
        return _hata("mavproxy.py bulunamadı. setup.sh kurulumu tamamlandı mı?")


def config_okunuyor_mu() -> bool:
    """config.yaml okunabiliyor ve temel alanlar var mı diye bakar."""
    try:
        cfg = ortak.config_oku()
    except SystemExit:
        return _hata("config.yaml okunamadı.")
    gerekli = ["pc_id", "ucus_no_araligi", "host", "udp_port", "tcp_port"]
    eksik = [a for a in gerekli if a not in cfg]
    if eksik:
        return _hata(f"config.yaml'da eksik alanlar: {eksik}")
    return _tamam(
        f"config.yaml okundu (pc_id={cfg['pc_id']}, "
        f"aralık={cfg['ucus_no_araligi']})."
    )


def port_bos_mu(host: str, port: int) -> bool:
    """Bir TCP portunun boş (dinlenmiyor) olup olmadığını raporlar."""
    if ortak.port_bos_mu(host, port):
        return _tamam(f"TCP {host}:{port} boş.")
    return _hata(
        f"TCP {host}:{port} dolu. Önceki SITL/proxy açık olabilir "
        "(pkill -f sim_vehicle; pkill -f kayit_proxy)."
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="AtaEtzel SITL kurulum sağlık kontrolü (Türkçe TAMAM/HATA)."
    )
    ap.parse_args()

    ortak.log("Sağlık kontrolü başlıyor...", "BILGI")
    cfg = ortak.config_oku()
    host = cfg.get("host", "127.0.0.1")
    tcp_port = int(cfg.get("tcp_port", 5760))

    sonuclar = [
        config_okunuyor_mu(),
        modul_import_edilebiliyor_mu("pymavlink"),
        mavproxy_var_mi(),
        modul_import_edilebiliyor_mu("pandas"),
        modul_import_edilebiliyor_mu("pyarrow"),
        arduplane_derlenmis_mi(),
        port_bos_mu(host, tcp_port),
    ]

    toplam = len(sonuclar)
    basarili = sum(1 for s in sonuclar if s)
    print("")
    if basarili == toplam:
        ortak.log(f"TÜM KONTROLLER TAMAM ({basarili}/{toplam}). Üretime hazırsınız.", "TAMAM")
        return 0
    ortak.log(
        f"{basarili}/{toplam} kontrol geçti. HATA satırlarını düzeltip tekrar deneyin.",
        "HATA",
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
