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
  7. Kalkıştan sonra meşru operatör komutları gönder (--operator-komut). Normal
     uçuşlarda komut olmazsa model "komut = saldırı" diye ezberler.
  8. Sonucu meta.json'a yaz. Kalkış doğrulanamazsa uçuş BAŞARISIZ sayılır ve
     betik 1 koduyla çıkar.

ÖNEMLİ: --speedup KULLANILMAZ. Simülasyonu hızlandırmak paketler arası
süreleri bozar; zamanlama öznitelikleri (paketler arası ort/std) buna
dayandığı için SIM hızı 1 kalmalıdır.

Kullanım:
    python betikler/ucus_yap.py --gorev gorevler/gorev1_dikdortgen.waypoints \
        --ucus F101_normal --sure 180 --ruzgar-hiz 3 --ruzgar-yon 90 --tohum 42
"""

from __future__ import annotations

import argparse
import json
import random
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
TELEMETRI_HIZI_HZ = 4            # varsayılan telemetri akış hızı

# Operatör komutları
OPERATOR_ARALIK_S = (20.0, 40.0)   # iki komut arası süre (ortalama 30 sn)
OPERATOR_SON_BOSLUK_S = 20.0       # uçuşun son 20 sn'sine komut konmaz
LOITER_SURE_S = (5.0, 12.0)        # AUTO -> LOITER -> AUTO döngüsünde LOITER süresi
DURUM_ARALIK_S = (12.0, 18.0)      # zararsız durum sorguları arası süre
ACK_ZAMAN_ASIMI_S = 3.0
YENIDEN_DENEME = 4                 # bozuk kanalda kaybolan yanıt için deneme sayısı
GOREV_YUKLEME_SURESI_S = 60.0
OPERATOR_ISLEMLERI = ("mod_dongusu", "hiz_degistir", "param_oku",
                      "gorev_sirasi", "mesaj_hizi")
OKUNACAK_PARAMLAR = ("WP_RADIUS", "WP_LOITER_RAD", "RTL_RADIUS", "RTL_ALTITUDE")
HIZI_DEGISEN_MESAJLAR = (30, 74, 65)     # ATTITUDE, VFR_HUD, RC_CHANNELS
SORGULANAN_MESAJLAR = (148, 242)         # AUTOPILOT_VERSION, HOME_POSITION
MAV_CMD_DO_CHANGE_SPEED = 178
MAV_CMD_SET_MESSAGE_INTERVAL = 511
MAV_CMD_REQUEST_MESSAGE = 512

# Görev irtifası
IRTIFALI_KOMUTLAR = {16, 18, 19, 22}     # WAYPOINT, LOITER_TURNS, LOITER_TIME, TAKEOFF
GORICELI_CERCEVE = 3                     # MAV_FRAME_GLOBAL_RELATIVE_ALT
EN_DUSUK_GOREV_IRTIFASI_M = 60.0         # kalkış eşiği 50 m'nin altına inilmez

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


def operator_plani(tohum: int, baslangic_s: float, bitis_s: float,
                   gorev_siralari: list[int]) -> list[dict]:
    """Meşru operatör komutlarının zaman planını üretir.

    Aynı girdiler aynı planı verir, böylece uçuş tekrar üretilebilir. Zamanlar
    uçuş başlangıcından itibaren saniyedir. tur: "ana" asıl operatör komutu,
    "donus" LOITER'dan AUTO'ya dönüş, "durum" zararsız durum sorgusudur.
    """
    rng = random.Random(tohum)
    plan: list[dict] = []
    t = baslangic_s
    while True:
        t += rng.uniform(*OPERATOR_ARALIK_S)
        if t >= bitis_s:
            break
        islem = rng.choice(OPERATOR_ISLEMLERI)
        loiter_s = rng.uniform(*LOITER_SURE_S)
        if islem == "gorev_sirasi" and not gorev_siralari:
            islem = "param_oku"
        if islem == "mod_dongusu" and t + loiter_s >= bitis_s:
            islem = "param_oku"

        if islem == "mod_dongusu":
            plan.append({"t_s": t, "komut": "mod", "parametre": "LOITER", "tur": "ana"})
            plan.append({"t_s": t + loiter_s, "komut": "mod", "parametre": "AUTO",
                         "tur": "donus"})
        elif islem == "hiz_degistir":
            plan.append({"t_s": t, "komut": "hiz_degistir",
                         "parametre": round(rng.uniform(18.0, 28.0), 1), "tur": "ana"})
        elif islem == "param_oku":
            plan.append({"t_s": t, "komut": "param_oku",
                         "parametre": rng.choice(OKUNACAK_PARAMLAR), "tur": "ana"})
        elif islem == "gorev_sirasi":
            plan.append({"t_s": t, "komut": "gorev_sirasi",
                         "parametre": rng.choice(gorev_siralari), "tur": "ana"})
        else:
            plan.append({"t_s": t, "komut": "mesaj_hizi", "tur": "ana",
                         "parametre": [rng.choice(HIZI_DEGISEN_MESAJLAR),
                                       rng.choice((2, 4, 10))]})

    # Durum sorguları ayrı bir sayı akışından gelir, ana komutları etkilemez.
    rng_durum = random.Random(tohum + 1)
    t = baslangic_s
    while True:
        t += rng_durum.uniform(*DURUM_ARALIK_S)
        if t >= bitis_s:
            break
        plan.append({"t_s": t, "komut": "durum_sorgusu",
                     "parametre": rng_durum.choice(SORGULANAN_MESAJLAR), "tur": "durum"})
    return sorted(plan, key=lambda adim: adim["t_s"])


class OperatorYurutucu:
    """Plandaki komutları zamanı gelince gönderir, yanıtları bekletmeden izler.

    Ana döngüyü durdurmaz: Kalkış izleme ve HEARTBEAT akışı sürer. Her kaydın
    ack alanı dolar: yanıt ya da "zaman_asimi".
    """

    def __init__(self, baglanti, plan: list[dict]) -> None:
        self.baglanti = baglanti
        self.plan = list(plan)
        self.kayitlar: list[dict] = []
        self.bekleyenler: list[dict] = []

    def _komut(self, komut: int, *parametreler: float) -> None:
        degerler = (list(parametreler) + [0.0] * 7)[:7]
        self.baglanti.mav.command_long_send(
            self.baglanti.target_system, self.baglanti.target_component,
            komut, 0, *degerler,
        )

    def gonder(self, adim: dict) -> None:
        komut, parametre = adim["komut"], adim["parametre"]
        kayit = {"t_ns": ortak.simdi_ns(), "komut": komut, "parametre": parametre,
                 "ack": None}
        if komut == "mod":
            self.baglanti.set_mode(self.baglanti.mode_mapping()[parametre])
            beklenen = ("COMMAND_ACK", 176)
        elif komut == "hiz_degistir":
            self._komut(MAV_CMD_DO_CHANGE_SPEED, 0, parametre, -1)
            beklenen = ("COMMAND_ACK", MAV_CMD_DO_CHANGE_SPEED)
        elif komut == "param_oku":
            self.baglanti.mav.param_request_read_send(
                self.baglanti.target_system, self.baglanti.target_component,
                parametre.encode("ascii"), -1,
            )
            beklenen = ("PARAM_VALUE", parametre)
        elif komut == "gorev_sirasi":
            self.baglanti.mav.mission_set_current_send(
                self.baglanti.target_system, self.baglanti.target_component, parametre,
            )
            beklenen = ("MISSION_CURRENT", parametre)
        elif komut == "mesaj_hizi":
            mesaj_no, hz = parametre
            self._komut(MAV_CMD_SET_MESSAGE_INTERVAL, mesaj_no, 1_000_000 / hz)
            beklenen = ("COMMAND_ACK", MAV_CMD_SET_MESSAGE_INTERVAL)
        else:  # durum_sorgusu
            self._komut(MAV_CMD_REQUEST_MESSAGE, parametre)
            beklenen = ("COMMAND_ACK", MAV_CMD_REQUEST_MESSAGE)
        self.kayitlar.append(kayit)
        self.bekleyenler.append({"kayit": kayit, "beklenen": beklenen,
                                 "son": time.time() + ACK_ZAMAN_ASIMI_S})

    def zamani_gelenleri_gonder(self, gecen_s: float) -> None:
        while self.plan and self.plan[0]["t_s"] <= gecen_s:
            self.gonder(self.plan.pop(0))

    def mesaj_isle(self, msg) -> None:
        tur = msg.get_type()
        if tur == "COMMAND_ACK":
            anahtar, sonuc = int(msg.command), int(msg.result)
        elif tur == "PARAM_VALUE":
            anahtar, sonuc = str(msg.param_id).rstrip("\x00"), "param_value"
        elif tur == "MISSION_CURRENT":
            anahtar, sonuc = int(msg.seq), "mission_current"
        else:
            return
        for bekleyen in self.bekleyenler:
            if bekleyen["beklenen"] == (tur, anahtar):
                bekleyen["kayit"]["ack"] = sonuc
                self.bekleyenler.remove(bekleyen)
                return

    def zaman_asimlarini_isle(self, hepsi: bool = False) -> None:
        simdi = time.time()
        for bekleyen in list(self.bekleyenler):
            if hepsi or simdi > bekleyen["son"]:
                bekleyen["kayit"]["ack"] = "zaman_asimi"
                self.bekleyenler.remove(bekleyen)


def ucus_sonucu_yaz(ucus_id: str, cfg: dict, kalkis: dict,
                    neden: str | None, ek: dict | None = None) -> None:
    """Uçuşun başarılı/başarısız sonucunu ve ek alanları meta.json'a işler."""
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
    meta.update(ek or {})
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


def irtifa_uygula(sira: int, komut: int, cerceve: int, irtifa_m: float,
                  fark_m: float) -> float:
    """Görev noktasının irtifasına farkı uygular, yeni irtifayı döndürür.

    Ev konumu (sıra 0), iniş ve RTL gibi irtifasız öğeler değişmez. Sonuç
    kalkış eşiğinin altına inmez.
    """
    if sira == 0 or komut not in IRTIFALI_KOMUTLAR or cerceve != GORICELI_CERCEVE:
        return irtifa_m
    return max(irtifa_m + fark_m, EN_DUSUK_GOREV_IRTIFASI_M)


def gorev_siralari(gorev_yolu: Path) -> list[int]:
    """Operatörün güvenle atlayabileceği görev noktaları (kalkış ve iniş hariç)."""
    siralar = []
    for satir in gorev_yolu.read_text(encoding="utf-8").splitlines()[1:]:
        alanlar = satir.split("\t")
        if len(alanlar) >= 12 and int(alanlar[0]) >= ILK_GOREV_SIRASI \
                and int(alanlar[3]) in IRTIFALI_KOMUTLAR:
            siralar.append(int(alanlar[0]))
    return siralar


def gorev_yukle(baglanti, gorev_yolu: Path, irtifa_farki_m: float = 0.0) -> int:
    """.waypoints dosyasını SITL'ye yükler.

    Yüklenen nokta sayısını döndürür; yükleme başarısızsa 0 döndürür.
    """
    wp = mavwp.MAVWPLoader(
        target_system=baglanti.target_system,
        target_component=baglanti.target_component,
    )
    sayi = wp.load(str(gorev_yolu))
    ortak.log(f"Görev okundu: {gorev_yolu.name} ({sayi} nokta).", "BILGI")
    for i in range(wp.count()):
        nokta = wp.wp(i)
        nokta.z = irtifa_uygula(i, nokta.command, nokta.frame, nokta.z, irtifa_farki_m)

    # Eski görevi sil. Yanıt kaybolabilir; yeniden denenir, sonuçsuz kalırsa da devam edilir.
    for _ in range(YENIDEN_DENEME):
        baglanti.waypoint_clear_all_send()
        if baglanti.recv_match(type=["MISSION_ACK"], blocking=True, timeout=3) is not None:
            break

    # Karşı taraf hangi noktayı isterse onu gönder; kayıpta isteğini tekrarlar.
    bitis = time.time() + GOREV_YUKLEME_SURESI_S
    baglanti.waypoint_count_send(wp.count())
    gonderilenler: set[int] = set()
    while time.time() < bitis:
        msg = baglanti.recv_match(
            type=["MISSION_REQUEST", "MISSION_REQUEST_INT", "MISSION_ACK"],
            blocking=True, timeout=3,
        )
        if msg is None:
            if len(gonderilenler) == wp.count():
                ortak.log("Son MISSION_ACK alınamadı; tüm noktalar gönderildi.", "UYARI")
                return wp.count()
            if not gonderilenler:
                baglanti.waypoint_count_send(wp.count())
            continue
        if msg.get_type() == "MISSION_ACK":
            if msg.type != mavutil.mavlink.MAV_MISSION_ACCEPTED:
                ortak.log(f"Görev kabul edilmedi (MISSION_ACK: {msg}).", "HATA")
                return 0
            ortak.log("Görev yüklendi (MISSION_ACK alındı).", "TAMAM")
            return wp.count()
        gonderilenler.add(msg.seq)
        baglanti.mav.send(wp.wp(msg.seq))
    ortak.log("Görev yükleme süresi doldu.", "HATA")
    return 0


def telemetri_iste(baglanti, hz: int = TELEMETRI_HIZI_HZ) -> None:
    """SITL'den telemetri akışını ister; yoksa konum mesajları gelmeyebilir."""
    baglanti.mav.request_data_stream_send(
        baglanti.target_system, baglanti.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_ALL, hz, 1,
    )


def hazir_bekle(baglanti, hz: int = TELEMETRI_HIZI_HZ,
                zaman_asimi_s: float = HAZIR_ZAMAN_ASIMI_S) -> bool:
    """GPS 3B fix ve ön-arm kontrolleri tamam olana kadar bekler.

    Arm komutunu deneme-yanılmayla göndermek yerine önce beklenir: reddedilen
    arm komutları normal uçuş verisine gereksiz ACK reddi olarak girerdi.
    """
    ortak.log("GPS ve ön-arm kontrolleri bekleniyor...", "BILGI")
    bitis = time.time() + zaman_asimi_s
    son_hb = 0.0
    prearm_tamam = gps_tamam = telemetri_var = False
    son_istek = time.time()
    while time.time() < bitis:
        if time.time() - son_hb >= 1.0:
            gcs_heartbeat(baglanti)
            son_hb = time.time()
        # Akış isteği bozuk kanalda kaybolmuş olabilir.
        if not telemetri_var and time.time() - son_istek >= 3.0:
            telemetri_iste(baglanti, hz)
            son_istek = time.time()
        msg = baglanti.recv_match(
            type=["SYS_STATUS", "GPS_RAW_INT"], blocking=True, timeout=1
        )
        if msg is None:
            continue
        telemetri_var = True
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
    for _ in range(YENIDEN_DENEME):
        baglanti.mav.param_set_send(
            baglanti.target_system,
            baglanti.target_component,
            ad.encode("ascii"),
            float(deger),
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
        )
        bitis = time.time() + ACK_ZAMAN_ASIMI_S
        while time.time() < bitis:
            msg = baglanti.recv_match(type=["PARAM_VALUE"], blocking=True, timeout=1)
            if msg is not None and str(msg.param_id).rstrip("\x00") == ad:
                ortak.log(f"Parametre ayarlandı: {ad} = {deger}", "BILGI")
                return
    ortak.log(f"Parametre doğrulanamadı: {ad}", "UYARI")


def mod_ayarla(baglanti, mod_adi: str) -> bool:
    """Uçuş modunu adıyla ayarlar (ör. AUTO, TAKEOFF). Kabul edildiyse True döndürür."""
    mod_haritasi = baglanti.mode_mapping()
    if mod_adi not in mod_haritasi:
        ortak.log(f"Mod bulunamadı: {mod_adi}", "UYARI")
        return False
    for _ in range(YENIDEN_DENEME):
        baglanti.set_mode(mod_haritasi[mod_adi])
        sonuc = komut_ack_bekle(baglanti, 176, ACK_ZAMAN_ASIMI_S)
        if sonuc == mavutil.mavlink.MAV_RESULT_ACCEPTED:
            ortak.log(f"Mod -> {mod_adi}", "BILGI")
            return True
        if sonuc is not None:
            break
    ortak.log(f"Mod değiştirilemedi: {mod_adi}", "HATA")
    return False


def komut_gonder(baglanti, komut: int, ad: str, *parametreler: float) -> bool:
    """COMMAND_LONG gönderir, ACK bekler. Kabul edildiyse True döndürür."""
    degerler = (list(parametreler) + [0.0] * 7)[:7]
    sonuc = None
    for _ in range(YENIDEN_DENEME):  # ACK gelmezse komut veya yanıt kaybolmuştur
        baglanti.mav.command_long_send(
            baglanti.target_system, baglanti.target_component, komut, 0, *degerler,
        )
        sonuc = komut_ack_bekle(baglanti, komut, ACK_ZAMAN_ASIMI_S)
        if sonuc is not None:
            break
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
        "--operator-komut", action=argparse.BooleanOptionalAction, default=True,
        help="Meşru operatör komutları gönder (kapatmak: --no-operator-komut).",
    )
    ap.add_argument("--tohum", type=int,
                    help="Operatör planının tohumu (yoksa rastgele seçilir, meta'ya yazılır).")
    ap.add_argument("--telemetri-hz", type=int, default=TELEMETRI_HIZI_HZ,
                    help="Telemetri akış hızı (Hz).")
    ap.add_argument("--irtifa-farki-m", type=float, default=0.0,
                    help="Görev irtifalarına eklenecek fark (metre).")
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
    tohum = args.tohum if args.tohum is not None else random.SystemRandom().randrange(2**31)
    operator: OperatorYurutucu | None = None

    def ek_alanlar() -> dict:
        kayitlar = operator.kayitlar if operator else []
        return {
            "tohum": tohum,
            "telemetri_hz": args.telemetri_hz,
            "irtifa_farki_m": args.irtifa_farki_m,
            "operator_komutlari": kayitlar,
        }

    def basarisiz(neden: str) -> int:
        ortak.log(f"UÇUŞ BAŞARISIZ: {neden}", "HATA")
        if operator:
            operator.zaman_asimlarini_isle(hepsi=True)
        ucus_sonucu_yaz(ucus_id, cfg, izleyici.sonuc(), neden, ek_alanlar())
        baglanti.close()
        return 1

    telemetri_iste(baglanti, args.telemetri_hz)

    # Rüzgâr
    if args.ruzgar_hiz or args.ruzgar_yon:
        param_ayarla(baglanti, "SIM_WIND_SPD", args.ruzgar_hiz)
        param_ayarla(baglanti, "SIM_WIND_DIR", args.ruzgar_yon)

    # Görev
    if gorev_yukle(baglanti, gorev_yolu, args.irtifa_farki_m) == 0:
        return basarisiz("görev yüklenemedi")

    if not hazir_bekle(baglanti, args.telemetri_hz):
        return basarisiz("GPS/ön-arm kontrolleri süresinde tamamlanmadı")

    # Arm + AUTO + kalkış
    ortak.log("Arm ediliyor...", "BILGI")
    if not komut_gonder(baglanti, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                        "Arm", 1):
        return basarisiz("arm komutu kabul edilmedi")
    if not mod_ayarla(baglanti, "AUTO"):
        return basarisiz("AUTO moduna geçilemedi")
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
                if args.operator_komut:
                    plan = operator_plani(
                        tohum, time.time() - baslangic,
                        args.sure - OPERATOR_SON_BOSLUK_S, gorev_siralari(gorev_yolu),
                    )
                    operator = OperatorYurutucu(baglanti, plan)
                    ortak.log(f"Operatör planı hazır: {len(plan)} adım (tohum {tohum}).", "BILGI")
            if operator:
                operator.mesaj_isle(msg)
        if operator:
            operator.zamani_gelenleri_gonder(time.time() - baslangic)
            operator.zaman_asimlarini_isle()
        if (not izleyici.dogrulandi
                and time.time() - baslangic > args.kalkis_zaman_asimi):
            return basarisiz(f"kalkış doğrulanamadı: {izleyici.neden()}")

    if not izleyici.dogrulandi:
        return basarisiz(f"kalkış doğrulanamadı: {izleyici.neden()}")

    if operator:
        operator.zaman_asimlarini_isle(hepsi=True)
    ucus_sonucu_yaz(ucus_id, cfg, izleyici.sonuc(), None, ek_alanlar())
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
