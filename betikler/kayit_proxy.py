#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kayit_proxy.py — MAVLink kayıt proxy'si (bu projenin kalbi).

Yer istasyonu (MAVProxy) ve saldırgan betikleri ile ArduPlane SITL
arasına girer; İKİ YÖNDEKİ her MAVLink paketini zaman damgasıyla
paketler.parquet'e kaydeder. İleride bu proxy, MAVLink güvenlik
duvarının iskeleti olacaktır.

Mimari:
    GCS / saldırgan  --UDP 14550-->  [BU PROXY]  --TCP 5760-->  ArduPlane SITL
    SITL telemetrisi de bu proxy üzerinden 14550'ye yazan HERKESE geri döner.

    Havadan enjeksiyon (sahte telemetri):
    saldırgan  --UDP 14551-->  [BU PROXY]  --UDP-->  GCS adresleri
    Bu paketler SITL'ye İLETİLMEZ. Yer istasyonunu hedefler ama duvar onları
    telsizden gelirken gördüğü için gcs2uav olarak kaydedilir (MIMARI.md,
    telsiz kanalı varsayımı).

Yönler:
    gcs2uav : UDP 14550'den gelen paket -> SITL'ye (TCP 5760) iletilir.
    uav2gcs : SITL'den gelen paket -> 14550'ye yazmış tüm adreslere geri gider.

Kayıt şeması (paketler.parquet) VERI_SEMASI.md ile birebir aynıdır.
UYARI: src_ip, src_port ve raw_hex yalnızca etiketleme/replay içindir;
bunlar ASLA öznitelik olarak modele verilmez (veri sızıntısı olur).

Kullanım:
    python betikler/kayit_proxy.py --ucus F101_normal
    python betikler/kayit_proxy.py            # otomatik sonraki normal numara

Durdurma: Ctrl+C. Kapanırken kalan kuyruk diske yazılır ve meta.json güncellenir.
Beklenmedik kapanma sonrası: python betikler/kayit_proxy.py --kurtar F101_normal
"""

from __future__ import annotations

import argparse
import json
import random
import select
import signal
import socket
import sys
import time
from datetime import date
from pathlib import Path

import kanal as kanal_modulu
import kayit_yazici
import ortak

try:
    from pymavlink import mavutil
    from pymavlink.dialects.v20 import ardupilotmega as mavlink2
except ImportError:
    mavutil = None
    mavlink2 = None


# paketler.parquet sütunları kayit_yazici.py içindeki açık şemada tanımlıdır.
SUTUNLAR = kayit_yazici.SUTUNLAR


class KayitProxy:
    """UDP (GCS tarafı) ile TCP (SITL tarafı) arasında köprü + kayıt."""

    def __init__(self, ucus_id: str, cfg: dict,
                 kanal: kanal_modulu.Kanal | None = None) -> None:
        self.cfg = cfg
        self.kanal = kanal or kanal_modulu.Kanal()
        self.ucus_id = ucus_id
        self.host = cfg.get("host", "127.0.0.1")
        self.udp_port = int(cfg.get("udp_port", 14550))
        self.tcp_port = int(cfg.get("tcp_port", 5760))
        self.enjeksiyon_port = int(cfg.get("hava_enjeksiyon_port", 14551))
        self.raw_hex_kaydet = bool(cfg.get("raw_hex_kaydet", True))

        self.klasor = ortak.ucus_klasoru_hazirla(ucus_id, cfg)
        self.parquet_yolu = self.klasor / "paketler.parquet"
        self.meta_yolu = self.klasor / "meta.json"

        # 14550'ye yazan GCS/saldırgan adresleri (telemetriyi geri yollamak için).
        self.gcs_adresleri: set[tuple[str, int]] = set()
        # 14551'e yazan adresler: telemetriyi kanaldan dinleyen saldırganı temsil eder.
        self.dinleyen_adresler: set[tuple[str, int]] = set()

        # Tampon ve sayaçlar
        self.yazici = kayit_yazici.AkisYazici(self.parquet_yolu)
        self.toplam_paket = 0
        # Doluysa her döngü adımının işlem süresi buraya yazılır (performans ölçümü).
        self.dongu_sureleri_ns: list[int] | None = None
        self.baslangic_ns = ortak.simdi_ns()

        # MAVLink çözümleyiciler (her yön için ayrı, seq takibi doğru olsun)
        self._mav_gcs = self._ayristirici_olustur()
        self._mav_uav = self._ayristirici_olustur()
        self._mav_enjeksiyon = self._ayristirici_olustur()

        self.udp_sok: socket.socket | None = None
        self.enjeksiyon_sok: socket.socket | None = None
        self.tcp_sok: socket.socket | None = None
        self.calisiyor = True

    @staticmethod
    def _ayristirici_olustur():
        """Hata toleranslı MAVLink ayrıştırıcısı oluşturur.

        SITL bağlantının başında MAVLink olmayan bayt gönderir. Varsayılan modda
        pymavlink burada hata verip saniyelerce mesaj çıkarmaz, sonra hepsini
        birden verir: paketler yanlış zamanla damgalanır. robust_parsing bozuk
        baytları atlayıp hemen devam eder; zaman damgalarının doğruluğu buna
        bağlıdır.
        """
        if mavlink2 is None:
            return None
        mav = mavlink2.MAVLink(None)
        mav.robust_parsing = True
        return mav

    # -----------------------------------------------------------------
    # Soket kurulumu
    # -----------------------------------------------------------------
    def soketleri_ac(self) -> None:
        # GÜVENLİK: Tüm soketler yalnızca localhost'a açılır; ilk iş bu kontroldür.
        ortak.localhost_dogrula(self.host)

        # UDP: GCS/saldırgan buraya yazar.
        self.udp_sok = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sok.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_sok.bind((self.host, self.udp_port))
        self.udp_sok.setblocking(False)
        ortak.log(f"UDP {self.host}:{self.udp_port} dinleniyor (GCS/saldırgan tarafı).", "TAMAM")

        # UDP: Havadan enjeksiyon girişi.
        self.enjeksiyon_sok = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.enjeksiyon_sok.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.enjeksiyon_sok.bind((self.host, self.enjeksiyon_port))
        self.enjeksiyon_sok.setblocking(False)
        ortak.log(f"UDP {self.host}:{self.enjeksiyon_port} dinleniyor (havadan enjeksiyon).", "TAMAM")

        # TCP: SITL'ye bağlan.
        self.tcp_sok = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.tcp_sok.connect((self.host, self.tcp_port))
        except OSError as e:
            ortak.hata_ve_cik(
                f"SITL'ye bağlanılamadı ({self.host}:{self.tcp_port}): {e}. "
                "Önce SITL'yi başlatın: "
                "cd ~/ardupilot/ArduPlane && sim_vehicle.py -v ArduPlane --no-mavproxy"
            )
        self.tcp_sok.setblocking(False)
        ortak.log(f"SITL'ye bağlandı (TCP {self.host}:{self.tcp_port}).", "TAMAM")

    # -----------------------------------------------------------------
    # Paket çözümleme ve kayıt
    # -----------------------------------------------------------------
    def _paketleri_coz(self, mav, veri: bytes, direction: str,
                       src_ip: str, src_port: int) -> list[bytes]:
        """Ham baytı mesajlara ayırıp kaydeder; mesajların ham baytlarını döndürür."""
        t_ns = ortak.simdi_ns()
        if mav is None:
            # pymavlink yoksa yalnızca ham kaydı tut (çözümsüz).
            self._tampona_ekle({
                "t_ns": t_ns, "direction": direction, "src_ip": src_ip,
                "src_port": src_port, "sysid": -1, "compid": -1, "seq": -1,
                "msgid": -1, "msgname": "RAW", "length": len(veri),
                "is_signed": False, "crc_ok": False, "fields_json": "{}",
                "raw_hex": veri.hex() if self.raw_hex_kaydet else "",
            })
            return [veri]
        try:
            mesajlar = mav.parse_buffer(veri) or []
        except Exception as e:
            ortak.log(f"{direction}: MAVLink ayrıştırma hatası: {e}", "UYARI")
            mesajlar = []
        hamlar: list[bytes] = []
        for m in mesajlar:
            if m.get_type() == "BAD_DATA":
                continue
            ham = bytes(m.get_msgbuf())
            hamlar.append(ham)
            try:
                alanlar = m.to_dict()
                alanlar.pop("mavpackon", None)
                fields_json = json.dumps(alanlar, default=str, ensure_ascii=False)
            except Exception:
                fields_json = "{}"
            self._tampona_ekle({
                "t_ns": t_ns,
                "direction": direction,
                "src_ip": src_ip,
                "src_port": src_port,
                "sysid": m.get_srcSystem(),
                "compid": m.get_srcComponent(),
                "seq": m.get_seq(),
                "msgid": m.get_msgId(),
                "msgname": m.get_type(),
                "length": len(ham),
                "is_signed": bool(getattr(m, "_msgbuf", b"") and (ham[0] == 0xFD and (ham[2] & 0x01))),
                "crc_ok": True,  # parse_buffer yalnızca CRC'si doğru mesaj döndürür
                "fields_json": fields_json,
                "raw_hex": ham.hex() if self.raw_hex_kaydet else "",
            })
        return hamlar

    def gcs_paketi_al(self, veri: bytes, adres: tuple[str, int]) -> None:
        """14550'den gelen paket: Telsizden geçmiş sayılır, kayıt bozulmadan sonradır."""
        self.gcs_adresleri.add(adres)
        self.kanal.gonder("gcs2uav", lambda: self._sitlye_ilet(veri, adres))

    def _sitlye_ilet(self, veri: bytes, adres: tuple[str, int]) -> None:
        try:
            self.tcp_sok.sendall(veri)
        except OSError as e:
            ortak.log(f"SITL'ye iletim hatası: {e}", "UYARI")
        self._paketleri_coz(self._mav_gcs, veri, "gcs2uav", adres[0], adres[1])

    def uav_paketi_al(self, veri: bytes) -> None:
        """SITL'den gelen paket: Önce kaydedilir, bozulma telsize girerken uygulanır."""
        self._dinleyenlere_gonder(veri)
        if self.kanal.temiz:
            self._gcsye_ilet(veri)
            self._paketleri_coz(self._mav_uav, veri, "uav2gcs", self.host, self.tcp_port)
            return
        hamlar = self._paketleri_coz(self._mav_uav, veri, "uav2gcs", self.host, self.tcp_port)
        self.kanal.toplu_gonder(
            "uav2gcs", [lambda ham=ham: self._gcsye_ilet(ham) for ham in hamlar]
        )

    def _gcsye_ilet(self, veri: bytes) -> None:
        for adres in list(self.gcs_adresleri):
            try:
                self.udp_sok.sendto(veri, adres)
            except OSError:
                pass

    def enjeksiyonu_isle(self, veri: bytes, adres: tuple[str, int]) -> None:
        """14551'den gelen paketi yer istasyonuna iletir, SITL'ye GÖNDERMEZ.

        Kayıt duvarın gözündendir: Paket telsizden geldiği için yön gcs2uav,
        kaynak enjekte eden adrestir.
        """
        self.dinleyen_adresler.add(adres)
        self.kanal.gonder("gcs2uav", lambda: self._enjeksiyonu_ilet(veri, adres))

    def _enjeksiyonu_ilet(self, veri: bytes, adres: tuple[str, int]) -> None:
        self._gcsye_ilet(veri)
        self._paketleri_coz(self._mav_enjeksiyon, veri, "gcs2uav", adres[0], adres[1])

    def _dinleyenlere_gonder(self, veri: bytes) -> None:
        """Telemetrinin kopyasını kanalı dinleyen saldırgana verir (kayıt edilmez)."""
        for hedef in list(self.dinleyen_adresler):
            try:
                self.enjeksiyon_sok.sendto(veri, hedef)
            except OSError:
                pass

    def _tampona_ekle(self, satir: dict) -> None:
        """Paketi yazıcı kuyruğuna verir; disk beklenmez."""
        self.yazici.ekle(satir)
        self.toplam_paket += 1

    # -----------------------------------------------------------------
    # meta.json
    # -----------------------------------------------------------------
    def meta_baslat(self) -> None:
        meta = {
            "flight_id": self.ucus_id,
            "pc_id": self.cfg.get("pc_id"),
            "ardupilot_version": "Plane-4.7.2",
            "vehicle": "ArduPlane",
            "mission_file": None,
            "wind": {"speed": None, "dir": None},
            "location": "CMAC (SITL varsayılan)",
            "date": date.today().isoformat(),
            "operator": None,
            "duration_s": None,
            "kanal": self.kanal.ozet(),
            "notes": "kayit_proxy.py tarafından başlatıldı.",
        }
        with open(self.meta_yolu, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    def meta_guncelle_kapanis(self) -> None:
        if not self.meta_yolu.exists():
            return
        try:
            with open(self.meta_yolu, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = {}
        meta["duration_s"] = round((ortak.simdi_ns() - self.baslangic_ns) / 1e9, 1)
        meta["kanal"] = self.kanal.ozet()
        with open(self.meta_yolu, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    # -----------------------------------------------------------------
    # Ana döngü
    # -----------------------------------------------------------------
    def calistir(self) -> None:
        self.soketleri_ac()
        self.meta_baslat()
        self.yazici.baslat()
        ortak.log(f"Kayıt başladı: {self.ucus_id}. Durdurmak için Ctrl+C.", "BILGI")
        son_rapor = ortak.simdi_ns()

        while self.calisiyor:
            # Zamanı gelecek paket varsa select onu kaçırmayacak kadar bekler.
            kalan = self.kanal.sonraki_sure_s()
            bekleme = 0.5 if kalan is None else min(0.5, kalan)
            okunabilir, _, _ = select.select(
                [self.udp_sok, self.enjeksiyon_sok, self.tcp_sok], [], [], bekleme
            )
            adim_baslangic = time.perf_counter_ns()
            for sok in okunabilir:
                try:
                    if sok is self.udp_sok:
                        veri, adres = self.udp_sok.recvfrom(65535)
                        if veri:
                            self.gcs_paketi_al(veri, adres)
                    elif sok is self.enjeksiyon_sok:
                        veri, adres = self.enjeksiyon_sok.recvfrom(65535)
                        if veri:
                            self.enjeksiyonu_isle(veri, adres)
                    else:
                        veri = self.tcp_sok.recv(65535)
                        if not veri:
                            ortak.log("SITL bağlantısı kapandı.", "UYARI")
                            self.calisiyor = False
                            break
                        self.uav_paketi_al(veri)
                except BlockingIOError:
                    continue
            self.kanal.zamani_gelenleri_gonder()

            if self.dongu_sureleri_ns is not None and okunabilir:
                self.dongu_sureleri_ns.append(time.perf_counter_ns() - adim_baslangic)

            # Her ~5 sn'de bir hız raporu
            simdi = ortak.simdi_ns()
            if (simdi - son_rapor) / 1e9 >= 5.0:
                hiz = self.toplam_paket / max((simdi - self.baslangic_ns) / 1e9, 1e-9)
                ortak.log(
                    f"Toplam {self.toplam_paket} paket (~{hiz:.1f} paket/sn).",
                    "BILGI",
                )
                son_rapor = simdi

        self.kapat()

    def kapat(self) -> None:
        ortak.log("Kapanıyor; kalan kuyruk yazılıyor...", "BILGI")
        self.kanal.bosalt()
        self.yazici.kapat()
        self.meta_guncelle_kapanis()
        for s in (self.udp_sok, self.enjeksiyon_sok, self.tcp_sok):
            try:
                if s:
                    s.close()
            except Exception:
                pass
        ortak.log(
            f"Kayıt bitti. {self.toplam_paket} paket -> {self.parquet_yolu}",
            "TAMAM",
        )


def proxy_calistir(ucus_id: str, cfg: dict,
                   kanal: kanal_modulu.Kanal | None = None) -> None:
    """Proxy'yi başlatır; Ctrl+C ve SIGTERM'de düzgün kapanır."""
    proxy = KayitProxy(ucus_id, cfg, kanal)

    def _sinyal(imza, cerceve):  # noqa: ANN001, ARG001
        proxy.calisiyor = False

    signal.signal(signal.SIGINT, _sinyal)
    signal.signal(signal.SIGTERM, _sinyal)

    proxy.calistir()


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--ucus",
        help="Uçuş adı (ör. F101_normal). Verilmezse config aralığından "
        "sonraki normal numara otomatik üretilir.",
    )
    ap.add_argument(
        "--kurtar", metavar="UCUS_ID",
        help="Beklenmedik kapanan uçuşun parquet'ini kurtarma günlüğünden üretir.",
    )
    ap.add_argument("--kanal-profil", default="temiz",
                    help="config.yaml'daki kanal profili (temiz, hafif, orta, agir).")
    ap.add_argument("--kanal-gecikme-ms", type=float, help="Profili ezer: ortalama gecikme.")
    ap.add_argument("--kanal-jitter-ms", type=float, help="Profili ezer: gecikme titreşimi (±).")
    ap.add_argument("--kanal-kayip", type=float, help="Profili ezer: paket kaybı yüzdesi.")
    ap.add_argument("--kanal-tohum", type=int,
                    help="Kanal tohumu (yoksa rastgele seçilir, meta.json'a yazılır).")
    args = ap.parse_args()

    if args.kurtar:
        yol = ortak.ucus_klasoru(args.kurtar) / "paketler.parquet"
        if not kayit_yazici.kurtarma_yolu(yol).exists():
            ortak.hata_ve_cik(f"Kurtarma günlüğü yok: {args.kurtar}")
        ortak.log(f"{kayit_yazici.kurtar(yol)} paket kurtarıldı -> {yol}", "TAMAM")
        return 0

    if mavutil is None:
        ortak.log("pymavlink kurulu değil; paketler çözümlenemez. setup.sh çalıştırın.", "UYARI")

    cfg = ortak.config_oku()
    ucus_id = args.ucus or ortak.sonraki_ucus_id("normal", cfg)
    # Çakışma koruması: numara bu cihazın aralığında mı, daha önce kullanıldı mı?
    ortak.ucus_id_dogrula(ucus_id, cfg, yeni_kayit=True)

    tohum = args.kanal_tohum
    if tohum is None:
        tohum = random.SystemRandom().randrange(2**31)
    try:
        ayar = kanal_modulu.ayar_olustur(
            cfg, args.kanal_profil, tohum, args.kanal_gecikme_ms,
            args.kanal_jitter_ms, args.kanal_kayip,
        )
    except ValueError as e:
        ortak.hata_ve_cik(str(e))
    ortak.log(f"Kanal: {ayar}", "BILGI")

    proxy_calistir(ucus_id, cfg, kanal_modulu.Kanal(ayar))
    return 0


if __name__ == "__main__":
    sys.exit(main())
