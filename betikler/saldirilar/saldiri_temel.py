#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""saldiri_temel.py — Saldırı betiklerinin paylaştığı temel yardımcılar.

Buradaki yardımcılar TÜM saldırı betikleri tarafından kullanılır:
  - betikler/ dizinini import yoluna ekler (ortak.py erişimi),
  - GÜVENLİK: hedefin yalnızca localhost olmasını zorunlu kılar,
  - proxy'nin UDP 14550 portuna bağlanan bir MAVLink göndereni kurar,
  - başlangıç gecikmesini bekler,
  - saldırının start_ns/end_ns ve attacker_addr'ini ground_truth.json'a yazar.

Bu modül bir saldırı DEĞİLDİR; yalnızca ortak iskelettir.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# betikler/ dizinini import yoluna ekle (ortak.py buradadır).
_BETIKLER = Path(__file__).resolve().parent.parent
if str(_BETIKLER) not in sys.path:
    sys.path.insert(0, str(_BETIKLER))

import ortak  # noqa: E402

try:
    from pymavlink import mavutil  # noqa: E402
except ImportError:
    mavutil = None


def temel_arg_parser(aciklama: str):
    """Tüm saldırı betiklerinin paylaştığı ortak argümanları kuran parser."""
    import argparse

    ap = argparse.ArgumentParser(
        description=aciklama, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--ucus", required=True, help="Hedef uçuş adı (ör. F106_spoof_cmd).")
    ap.add_argument("--sure", type=float, default=30.0, help="Saldırı süresi (saniye).")
    ap.add_argument(
        "--baslangic-gecikme",
        type=float,
        default=0.0,
        help="Betik başladıktan kaç sn sonra saldırı başlasın.",
    )
    return ap


def gonderen_kur(cfg: dict, source_system: int = 255, source_component: int = 190,
                 port: int | None = None):
    """Proxy'nin UDP portuna (varsayılan 14550) bağlanan bir MAVLink göndereni kurar.

    GÜVENLİK: Bağlanmadan önce hedefin localhost olduğunu zorunlu kılar.
    Saldırı betikleri doğrudan SITL'ye DEĞİL, proxy'nin telsiz kanalına
    (UDP 14550) yazar; tıpkı gerçek bir saldırganın telsiz kanalına
    girmesi gibi.
    """
    if mavutil is None:
        ortak.hata_ve_cik("pymavlink kurulu değil. setup.sh çalıştırın.")

    host = cfg.get("host", "127.0.0.1")
    udp_port = int(port if port is not None else cfg.get("udp_port", 14550))

    # ---- GÜVENLİK KONTROLÜ (silmeyin) ----
    ortak.localhost_dogrula(host)

    baglanti = mavutil.mavlink_connection(
        f"udpout:{host}:{udp_port}",
        source_system=source_system,
        source_component=source_component,
    )
    return baglanti


def attacker_addr_al(baglanti, cfg: dict) -> str:
    """Saldırganın yerel soket adresini 'ip:port' olarak döndürür.

    etiketle.py bu adresi paketlerdeki src_ip/src_port ile eşleştirerek
    saldırı paketlerini işaretler. İlk paketten sonra çağrılmalıdır.
    """
    host = cfg.get("host", "127.0.0.1")
    try:
        ip, port = baglanti.port.getsockname()[:2]
        if ip in ("0.0.0.0", ""):
            ip = host
        return f"{ip}:{port}"
    except Exception:
        return host


def baslangic_gecikmesi_bekle(saniye: float) -> None:
    if saniye and saniye > 0:
        ortak.log(f"Başlangıç gecikmesi: {saniye} sn bekleniyor...", "BILGI")
        time.sleep(saniye)


def ground_truth_yaz(
    ucus_id: str,
    attack_type: str,
    start_ns: int,
    end_ns: int,
    attacker_addr: str,
    params: dict,
    cfg: dict,
) -> None:
    """Saldırı kaydını ground_truth.json'a ekler."""
    ortak.ground_truth_ekle(
        ucus_id,
        {
            "attack_type": attack_type,
            "start_ns": start_ns,
            "end_ns": end_ns,
            "attacker_addr": attacker_addr,
            "params": params,
        },
        cfg,
    )
