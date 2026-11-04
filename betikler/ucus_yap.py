#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ucus_yap.py — Bir normal uçuşı baştan sona otomatik yapar.

Bu betik YER İSTASYONU gibi davranır: doğrudan SITL'ye değil, PROXY'ye
(udpout:127.0.0.1:14550) bağlanır. Böylece gönderdiği her komut da
kayit_proxy.py tarafından kaydedilir.

Adımlar:
  1. Proxy'nin çalıştığını doğrula (14550'ye bağlanılabiliyor mu).
  2. Görev dosyasını (.waypoints) yükle (MISSION_COUNT/MISSION_ITEM).
  3. Rüzgârı ayarla (SIM_WIND_SPD / SIM_WIND_DIR).
  4. Arm et, AUTO moduna al, kalkışı başlat.
  5. --sure saniye boyunca veya görev bitene kadar uçur.
  6. meta.json'a görev, rüzgâr ve konum bilgisini yaz.

ÖNEMLİ: --speedup KULLANILMAZ. Simülasyonu hızlandırmak paketler arası
süreleri bozar; zamanlama öznitelikleri (paketler arası ort/std) buna
dayandığı için SIM hızı 1 kalmalıdır.

Kullanım:
    python betikler/ucus_yap.py --gorev gorevler/gorev1_dikdortgen.waypoints \
        --ucus F101_normal --sure 180 --ruzgar-hiz 3 --ruzgar-yon 90
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import ortak

try:
    from pymavlink import mavutil, mavwp
except ImportError:
    mavutil = None
    mavwp = None


def proxy_calisiyor_mu(host: str, udp_port: int) -> bool:
    """Proxy'ye UDP ile bağlanıp HEARTBEAT gelip gelmediğini kontrol eder."""
    if mavutil is None:
        return False
    try:
        baglanti = mavutil.mavlink_connection(
            f"udpout:{host}:{udp_port}", source_system=255
        )
        # Proxy üzerinden SITL'nin HEARTBEAT'ini bekle
        baglanti.mav.heartbeat_send(6, 8, 0, 0, 0)  # GCS kimliği
        hb = baglanti.wait_heartbeat(timeout=10)
        baglanti.close()
        return hb is not None
    except Exception:
        return False


def gorev_yukle(baglanti, gorev_yolu: Path) -> int:
    """QGC WPL 110 biçimli .waypoints dosyasını SITL'ye yükler. Nokta sayısı döner."""
    wp = mavwp.MAVWPLoader()
    sayi = wp.load(str(gorev_yolu))
    ortak.log(f"Görev okundu: {gorev_yolu.name} ({sayi} nokta).", "BILGI")

    baglanti.waypoint_clear_all_send()
    baglanti.waypoint_count_send(wp.count())
    for _ in range(wp.count()):
        msg = baglanti.recv_match(type=["MISSION_REQUEST"], blocking=True, timeout=10)
        if msg is None:
            ortak.log("Görev yükleme sırasında MISSION_REQUEST gelmedi.", "UYARI")
            break
        baglanti.mav.send(wp.wp(msg.seq))
    ack = baglanti.recv_match(type=["MISSION_ACK"], blocking=True, timeout=10)
    if ack is not None:
        ortak.log("Görev yüklendi (MISSION_ACK alındı).", "TAMAM")
    return wp.count()


def param_ayarla(baglanti, ad: str, deger: float) -> None:
    """Bir SITL parametresini ayarlar (ör. rüzgâr)."""
    baglanti.mav.param_set_send(
        baglanti.target_system,
        baglanti.target_component,
        ad.encode("ascii"),
        float(deger),
        mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
    )
    ortak.log(f"Parametre ayarlandı: {ad} = {deger}", "BILGI")


def mod_ayarla(baglanti, mod_adi: str) -> None:
    """Uçuş modunu adıyla ayarlar (ör. AUTO, TAKEOFF)."""
    mod_haritasi = baglanti.mode_mapping()
    if mod_adi not in mod_haritasi:
        ortak.log(f"Mod bulunamadı: {mod_adi}", "UYARI")
        return
    baglanti.set_mode(mod_haritasi[mod_adi])
    ortak.log(f"Mod -> {mod_adi}", "BILGI")


def meta_guncelle(ucus_id: str, cfg: dict, gorev: str, ruzgar_hiz, ruzgar_yon) -> None:
    """meta.json'a görev ve rüzgâr bilgisini yazar."""
    yol = ortak.ucus_klasoru(ucus_id, cfg) / "meta.json"
    meta = {}
    if yol.exists():
        try:
            meta = json.loads(yol.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    meta["flight_id"] = ucus_id
    meta["mission_file"] = gorev
    meta["wind"] = {"speed": ruzgar_hiz, "dir": ruzgar_yon}
    meta.setdefault("vehicle", "ArduPlane")
    meta.setdefault("ardupilot_version", "Plane-4.7.2")
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--gorev", required=True, help="Görev dosyası (.waypoints).")
    ap.add_argument("--ucus", help="Uçuş adı (yoksa otomatik numara).")
    ap.add_argument("--ruzgar-hiz", type=float, default=0.0, help="Rüzgâr hızı (m/s).")
    ap.add_argument("--ruzgar-yon", type=float, default=0.0, help="Rüzgâr yönü (derece).")
    ap.add_argument("--sure", type=int, default=180, help="Uçuş süresi (saniye).")
    args = ap.parse_args()

    if mavutil is None:
        ortak.hata_ve_cik("pymavlink kurulu değil. setup.sh çalıştırın.")

    cfg = ortak.config_oku()
    host = cfg.get("host", "127.0.0.1")
    udp_port = int(cfg.get("udp_port", 14550))
    ucus_id = args.ucus or ortak.sonraki_ucus_id("normal", cfg)
    # Klasörü proxy açtığı için burada yalnızca biçim/aralık denetlenir.
    ortak.ucus_id_dogrula(ucus_id, cfg)

    gorev_yolu = Path(args.gorev)
    if not gorev_yolu.exists():
        ortak.hata_ve_cik(f"Görev dosyası bulunamadı: {gorev_yolu}")

    ortak.log("Proxy çalışıyor mu kontrol ediliyor...", "BILGI")
    if not proxy_calisiyor_mu(host, udp_port):
        ortak.hata_ve_cik(
            f"Proxy'ye ({host}:{udp_port}) HEARTBEAT ile ulaşılamadı. "
            "Önce kayit_proxy.py'yi (ve SITL'yi) başlatın."
        )
    ortak.log("Proxy ve SITL erişilebilir.", "TAMAM")

    # Asıl bağlantı (yer istasyonu rolü, sysid=255)
    baglanti = mavutil.mavlink_connection(
        f"udpout:{host}:{udp_port}", source_system=255
    )
    baglanti.wait_heartbeat(timeout=10)
    ortak.log(
        f"SITL ile el sıkışıldı (sysid={baglanti.target_system}).", "TAMAM"
    )

    # Rüzgâr
    if args.ruzgar_hiz or args.ruzgar_yon:
        param_ayarla(baglanti, "SIM_WIND_SPD", args.ruzgar_hiz)
        param_ayarla(baglanti, "SIM_WIND_DIR", args.ruzgar_yon)

    # Görev
    gorev_yukle(baglanti, gorev_yolu)

    # Arm + AUTO + kalkış
    ortak.log("Arm ediliyor...", "BILGI")
    baglanti.arducopter_arm() if hasattr(baglanti, "arducopter_arm") else None
    baglanti.mav.command_long_send(
        baglanti.target_system, baglanti.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1, 0, 0, 0, 0, 0, 0,
    )
    time.sleep(2)
    mod_ayarla(baglanti, "AUTO")
    # ArduPlane AUTO modunda otomatik kalkış için
    baglanti.mav.command_long_send(
        baglanti.target_system, baglanti.target_component,
        mavutil.mavlink.MAV_CMD_MISSION_START, 0, 0, 0, 0, 0, 0, 0, 0,
    )
    ortak.log(f"Uçuş başladı. {args.sure} sn boyunca uçulacak...", "BILGI")

    meta_guncelle(ucus_id, cfg, gorev_yolu.name, args.ruzgar_hiz, args.ruzgar_yon)

    baslangic = time.time()
    while time.time() - baslangic < args.sure:
        msg = baglanti.recv_match(blocking=True, timeout=1)
        if msg is None:
            continue
        # Görev bittiyse (MISSION_ITEM_REACHED son noktaya ulaştıysa) erken çık
        # Basitlik için yalnızca süreye göre durduruyoruz.

    ortak.log("Süre doldu. Uçuş tamamlandı.", "TAMAM")
    print("")
    ortak.log(
        f"ÖZET: uçuş={ucus_id}, görev={gorev_yolu.name}, süre={args.sure}sn, "
        f"rüzgâr={args.ruzgar_hiz}m/s @ {args.ruzgar_yon}°",
        "TAMAM",
    )
    baglanti.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
