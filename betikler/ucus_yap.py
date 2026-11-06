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
  4. Telemetri akışını iste, GPS/EKF hazır olana kadar bekle.
  5. Arm et, AUTO moduna al, kalkışı başlat (her komutun ACK'i beklenir).
  6. --sure saniye boyunca uçur; bu sırada kalkışı doğrula: irtifa > 50 m ve
     AUTO modunda waypoint ilerlemesi (HEARTBEAT, GLOBAL_POSITION_INT).
  7. Sonucu meta.json'a yaz. Kalkış doğrulanamazsa uçuş BAŞARISIZ sayılır ve
     betik 1 koduyla çıkar.

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


# Kalkış doğrulama eşikleri
KALKIS_IRTIFA_ESIGI_M = 50.0
KALKIS_ZAMAN_ASIMI_S = 120.0     # kalkıştan sonra doğrulama için tanınan süre
HAZIR_ZAMAN_ASIMI_S = 180.0      # GPS/EKF hazır olması için tanınan süre
TELEMETRI_HIZI_HZ = 4            # istenen telemetri akış hızı

# MAVLink sabitleri (pymavlink olmadan da test edilebilsin diye burada)
PLANE_AUTO_MODU = 10             # ArduPlane custom_mode: AUTO
MAV_TYPE_GCS = 6
ARMED_BAYRAGI = 128              # MAV_MODE_FLAG_SAFETY_ARMED
PREARM_BITI = 0x10000000         # MAV_SYS_STATUS_PREARM_CHECK
GPS_3D_FIX = 3
ILK_GOREV_SIRASI = 2             # 0=home, 1=kalkış, 2=ilk gerçek görev noktası


class KalkisIzleyici:
    """Uçağın gerçekten kalktığını telemetriden doğrular.

    MAVLink'ten bağımsızdır (yalnızca get_type() ve alanları kullanır), bu
    yüzden SITL olmadan da test edilebilir. Bir koşul bir kez sağlandıysa
    sağlanmış kalır: uçuşun ilerleyen bölümünde saldırı uçağı indirse bile
    kalkış olmuştur.
    """

    def __init__(self, irtifa_esigi_m: float = KALKIS_IRTIFA_ESIGI_M) -> None:
        self.irtifa_esigi_m = irtifa_esigi_m
        self.armed_goruldu = False
        self.auto_goruldu = False
        self.maks_irtifa_m = 0.0
        self.waypoint_ilerlemesi = False
        self.son_gorev_sirasi: int | None = None
        self._armed = False
        self._auto = False

    def mesaj_isle(self, msg) -> None:
        tur = msg.get_type()
        if tur == "HEARTBEAT":
            if msg.type == MAV_TYPE_GCS:
                return
            self._armed = bool(msg.base_mode & ARMED_BAYRAGI)
            self._auto = msg.custom_mode == PLANE_AUTO_MODU
            self.armed_goruldu = self.armed_goruldu or self._armed
            self.auto_goruldu = self.auto_goruldu or (self._armed and self._auto)
        elif tur == "GLOBAL_POSITION_INT":
            self.maks_irtifa_m = max(self.maks_irtifa_m, msg.relative_alt / 1000.0)
        elif tur == "MISSION_CURRENT":
            sira = int(msg.seq)
            if (self._armed and self._auto and self.son_gorev_sirasi is not None
                    and sira > self.son_gorev_sirasi and sira >= ILK_GOREV_SIRASI):
                self.waypoint_ilerlemesi = True
            self.son_gorev_sirasi = sira
        elif tur == "MISSION_ITEM_REACHED":
            if self._armed and self._auto and int(msg.seq) >= ILK_GOREV_SIRASI:
                self.waypoint_ilerlemesi = True

    @property
    def dogrulandi(self) -> bool:
        return (self.auto_goruldu
                and self.maks_irtifa_m > self.irtifa_esigi_m
                and self.waypoint_ilerlemesi)

    def neden(self) -> str | None:
        """Doğrulanamadıysa ilk eksik koşulu Türkçe döndürür."""
        if self.dogrulandi:
            return None
        if not self.armed_goruldu:
            return "uçak arm olmadı"
        if not self.auto_goruldu:
            return "uçak AUTO moduna geçmedi"
        if self.maks_irtifa_m <= self.irtifa_esigi_m:
            return (f"irtifa {self.irtifa_esigi_m:.0f} m'yi geçmedi "
                    f"(en yüksek {self.maks_irtifa_m:.1f} m)")
        return "AUTO modunda waypoint ilerlemesi görülmedi"

    def sonuc(self) -> dict:
        return {
            "dogrulandi": self.dogrulandi,
            "armed_goruldu": self.armed_goruldu,
            "auto_goruldu": self.auto_goruldu,
            "maks_irtifa_m": round(self.maks_irtifa_m, 1),
            "waypoint_ilerlemesi": self.waypoint_ilerlemesi,
            "son_gorev_sirasi": self.son_gorev_sirasi,
        }


def ucus_sonucu_yaz(ucus_id: str, cfg: dict, kalkis: dict,
                    neden: str | None) -> None:
    """Uçuşun başarılı/başarısız sonucunu meta.json'a işler."""
    yol = ortak.ucus_klasoru(ucus_id, cfg) / "meta.json"
    meta = {}
    if yol.exists():
        try:
            meta = json.loads(yol.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    meta["flight_id"] = ucus_id
    meta["ucus_basarili"] = neden is None
    meta["basarisizlik_nedeni"] = neden
    meta["kalkis_kontrolu"] = kalkis
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def gcs_heartbeat(baglanti) -> None:
    """Yer istasyonu HEARTBEAT'i gönderir (gerçek bir GCS 1 Hz yollar)."""
    baglanti.mav.heartbeat_send(MAV_TYPE_GCS, 8, 0, 0, 0)


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
    """.waypoints dosyasını SITL'ye yükler.

    Yüklenen nokta sayısını döndürür; yükleme başarısızsa 0 döndürür.
    """
    wp = mavwp.MAVWPLoader(
        target_system=baglanti.target_system,
        target_component=baglanti.target_component,
    )
    sayi = wp.load(str(gorev_yolu))
    ortak.log(f"Görev okundu: {gorev_yolu.name} ({sayi} nokta).", "BILGI")

    baglanti.waypoint_clear_all_send()
    baglanti.waypoint_count_send(wp.count())
    for _ in range(wp.count()):
        msg = baglanti.recv_match(
            type=["MISSION_REQUEST", "MISSION_REQUEST_INT"], blocking=True, timeout=10
        )
        if msg is None:
            ortak.log("Görev yükleme sırasında MISSION_REQUEST gelmedi.", "HATA")
            return 0
        baglanti.mav.send(wp.wp(msg.seq))
    ack = baglanti.recv_match(type=["MISSION_ACK"], blocking=True, timeout=10)
    if ack is None or ack.type != mavutil.mavlink.MAV_MISSION_ACCEPTED:
        ortak.log(f"Görev kabul edilmedi (MISSION_ACK: {ack}).", "HATA")
        return 0
    ortak.log("Görev yüklendi (MISSION_ACK alındı).", "TAMAM")
    return wp.count()


def telemetri_iste(baglanti) -> None:
    """SITL'den telemetri akışını ister; yoksa konum mesajları gelmeyebilir."""
    baglanti.mav.request_data_stream_send(
        baglanti.target_system, baglanti.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_ALL, TELEMETRI_HIZI_HZ, 1,
    )


def hazir_bekle(baglanti, zaman_asimi_s: float = HAZIR_ZAMAN_ASIMI_S) -> bool:
    """GPS 3B fix ve ön-arm kontrolleri tamam olana kadar bekler.

    Arm komutunu deneme-yanılmayla göndermek yerine önce beklenir: reddedilen
    arm komutları normal uçuş verisine gereksiz ACK reddi olarak girerdi.
    """
    ortak.log("GPS ve ön-arm kontrolleri bekleniyor...", "BILGI")
    bitis = time.time() + zaman_asimi_s
    son_hb = 0.0
    prearm_tamam = gps_tamam = False
    while time.time() < bitis:
        if time.time() - son_hb >= 1.0:
            gcs_heartbeat(baglanti)
            son_hb = time.time()
        msg = baglanti.recv_match(
            type=["SYS_STATUS", "GPS_RAW_INT"], blocking=True, timeout=1
        )
        if msg is None:
            continue
        if msg.get_type() == "SYS_STATUS":
            prearm_tamam = bool(msg.onboard_control_sensors_health & PREARM_BITI)
        else:
            gps_tamam = msg.fix_type >= GPS_3D_FIX
        if prearm_tamam and gps_tamam:
            ortak.log("Uçak arm için hazır.", "TAMAM")
            return True
    ortak.log(
        f"{zaman_asimi_s:.0f} sn içinde hazır olmadı "
        f"(ön-arm={prearm_tamam}, gps={gps_tamam}).", "HATA",
    )
    return False


def komut_ack_bekle(baglanti, komut: int, zaman_asimi_s: float = 5.0) -> int | None:
    """Verilen komutun COMMAND_ACK sonucunu döndürür; gelmezse None."""
    bitis = time.time() + zaman_asimi_s
    while time.time() < bitis:
        msg = baglanti.recv_match(
            type=["COMMAND_ACK"], blocking=True, timeout=max(0.1, bitis - time.time())
        )
        if msg is not None and msg.command == komut:
            return int(msg.result)
    return None


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


def komut_gonder(baglanti, komut: int, ad: str, *parametreler: float) -> bool:
    """COMMAND_LONG gönderir, ACK bekler. Kabul edildiyse True döndürür."""
    degerler = (list(parametreler) + [0.0] * 7)[:7]
    baglanti.mav.command_long_send(
        baglanti.target_system, baglanti.target_component, komut, 0, *degerler,
    )
    sonuc = komut_ack_bekle(baglanti, komut)
    if sonuc == mavutil.mavlink.MAV_RESULT_ACCEPTED:
        ortak.log(f"{ad} kabul edildi.", "TAMAM")
        return True
    ortak.log(f"{ad} kabul edilmedi (ACK sonucu: {sonuc}).", "HATA")
    return False


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
    ap.add_argument(
        "--kalkis-zaman-asimi", type=float, default=KALKIS_ZAMAN_ASIMI_S,
        help="Kalkış bu kadar saniyede doğrulanmazsa uçuş başarısız sayılır.",
    )
    ap.add_argument(
        "--kalkis-isareti",
        help="Kalkış doğrulanınca oluşturulacak dosya (saldırı betiği bunu bekler).",
    )
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
    # udpout bağlantısında proxy adresimizi ancak ilk paketimizden öğrenir;
    # bu yüzden önce biz HEARTBEAT göndeririz.
    gcs_heartbeat(baglanti)
    if baglanti.wait_heartbeat(timeout=10) is None:
        ortak.hata_ve_cik("Ana bağlantıda SITL HEARTBEAT'i alınamadı.")
    ortak.log(
        f"SITL ile el sıkışıldı (sysid={baglanti.target_system}).", "TAMAM"
    )
    meta_guncelle(ucus_id, cfg, gorev_yolu.name, args.ruzgar_hiz, args.ruzgar_yon)
    izleyici = KalkisIzleyici()

    def basarisiz(neden: str) -> int:
        ortak.log(f"UÇUŞ BAŞARISIZ: {neden}", "HATA")
        ucus_sonucu_yaz(ucus_id, cfg, izleyici.sonuc(), neden)
        baglanti.close()
        return 1

    telemetri_iste(baglanti)

    # Rüzgâr
    if args.ruzgar_hiz or args.ruzgar_yon:
        param_ayarla(baglanti, "SIM_WIND_SPD", args.ruzgar_hiz)
        param_ayarla(baglanti, "SIM_WIND_DIR", args.ruzgar_yon)

    # Görev
    if gorev_yukle(baglanti, gorev_yolu) == 0:
        return basarisiz("görev yüklenemedi")

    if not hazir_bekle(baglanti):
        return basarisiz("GPS/ön-arm kontrolleri süresinde tamamlanmadı")

    # Arm + AUTO + kalkış
    ortak.log("Arm ediliyor...", "BILGI")
    if not komut_gonder(baglanti, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                        "Arm", 1):
        return basarisiz("arm komutu kabul edilmedi")
    mod_ayarla(baglanti, "AUTO")
    # ArduPlane AUTO modunda otomatik kalkış için
    if not komut_gonder(baglanti, mavutil.mavlink.MAV_CMD_MISSION_START,
                        "MISSION_START"):
        return basarisiz("MISSION_START kabul edilmedi")
    ortak.log(f"Uçuş başladı. {args.sure} sn boyunca uçulacak...", "BILGI")

    baslangic = time.time()
    son_hb = 0.0
    while time.time() - baslangic < args.sure:
        if time.time() - son_hb >= 1.0:
            gcs_heartbeat(baglanti)
            son_hb = time.time()
        msg = baglanti.recv_match(blocking=True, timeout=1)
        if msg is not None:
            onceki = izleyici.dogrulandi
            izleyici.mesaj_isle(msg)
            if izleyici.dogrulandi and not onceki:
                ortak.log(
                    f"Kalkış doğrulandı: irtifa {izleyici.maks_irtifa_m:.1f} m, "
                    "AUTO'da waypoint ilerlemesi var.", "TAMAM",
                )
                if args.kalkis_isareti:
                    Path(args.kalkis_isareti).touch()
        if (not izleyici.dogrulandi
                and time.time() - baslangic > args.kalkis_zaman_asimi):
            return basarisiz(f"kalkış doğrulanamadı: {izleyici.neden()}")

    if not izleyici.dogrulandi:
        return basarisiz(f"kalkış doğrulanamadı: {izleyici.neden()}")

    ucus_sonucu_yaz(ucus_id, cfg, izleyici.sonuc(), None)
    ortak.log("Süre doldu. Uçuş tamamlandı.", "TAMAM")
    print("")
    ortak.log(
        f"ÖZET: uçuş={ucus_id}, görev={gorev_yolu.name}, süre={args.sure}sn, "
        f"rüzgâr={args.ruzgar_hiz}m/s @ {args.ruzgar_yon}°, "
        f"en yüksek irtifa={izleyici.maks_irtifa_m:.1f} m",
        "TAMAM",
    )
    baglanti.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
