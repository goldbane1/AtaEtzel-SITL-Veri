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

Durdurma: Ctrl+C. Kapanırken kalan tampon diske yazılır ve meta.json güncellenir.
"""

from __future__ import annotations

import argparse
import json
import select
import signal
import socket
import sys
from datetime import date
from pathlib import Path

import ortak

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from pymavlink import mavutil
    from pymavlink.dialects.v20 import ardupilotmega as mavlink2
except ImportError:
    mavutil = None
    mavlink2 = None


# paketler.parquet sütun sırası (VERI_SEMASI.md ile birebir).
SUTUNLAR = [
    "t_ns", "direction", "src_ip", "src_port", "sysid", "compid",
    "seq", "msgid", "msgname", "length", "is_signed", "crc_ok",
    "fields_json", "raw_hex",
]

# Tamponu diske yazma eşiği (paket adedi) ve süre (saniye).
TAMPON_PAKET_ESIGI = 500
TAMPON_SURE_ESIGI = 2.0


class KayitProxy:
    """UDP (GCS tarafı) ile TCP (SITL tarafı) arasında köprü + kayıt."""

    def __init__(self, ucus_id: str, cfg: dict) -> None:
        self.cfg = cfg
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
        self.tampon: list[dict] = []
        self.toplam_paket = 0
        self.son_yazma = ortak.simdi_ns()
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
                       src_ip: str, src_port: int) -> None:
        """Ham baytı MAVLink mesajlarına ayrıştırıp tampona ekler."""
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
            return
        try:
            mesajlar = mav.parse_buffer(veri) or []
        except Exception as e:
            ortak.log(f"{direction}: MAVLink ayrıştırma hatası: {e}", "UYARI")
            mesajlar = []
        for m in mesajlar:
            if m.get_type() == "BAD_DATA":
                continue
            ham = m.get_msgbuf()
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

    def enjeksiyonu_isle(self, veri: bytes, adres: tuple[str, int]) -> None:
        """14551'den gelen paketi yer istasyonuna iletir, SITL'ye GÖNDERMEZ.

        Kayıt duvarın gözündendir: Paket telsizden geldiği için yön gcs2uav,
        kaynak enjekte eden adrestir.
        """
        self.dinleyen_adresler.add(adres)
        for hedef in list(self.gcs_adresleri):
            try:
                self.udp_sok.sendto(veri, hedef)
            except OSError:
                pass
        self._paketleri_coz(self._mav_enjeksiyon, veri, "gcs2uav", adres[0], adres[1])

    def _dinleyenlere_gonder(self, veri: bytes) -> None:
        """Telemetrinin kopyasını kanalı dinleyen saldırgana verir (kayıt edilmez)."""
        for hedef in list(self.dinleyen_adresler):
            try:
                self.enjeksiyon_sok.sendto(veri, hedef)
            except OSError:
                pass

    def _tampona_ekle(self, satir: dict) -> None:
        self.tampon.append(satir)
        self.toplam_paket += 1
        simdi = ortak.simdi_ns()
        sure_gecti = (simdi - self.son_yazma) / 1e9 >= TAMPON_SURE_ESIGI
        if len(self.tampon) >= TAMPON_PAKET_ESIGI or sure_gecti:
            self.tamponu_yaz()

    def tamponu_yaz(self) -> None:
        """Tampondaki satırları parquet'e EKLER (append) ve tamponu boşaltır."""
        if not self.tampon:
            self.son_yazma = ortak.simdi_ns()
            return
        if pd is None:
            ortak.log("pandas yok; parquet'e yazılamıyor. Tampon atlandı.", "UYARI")
            self.tampon.clear()
            return
        yeni = pd.DataFrame(self.tampon, columns=SUTUNLAR)
        if self.parquet_yolu.exists():
            eski = pd.read_parquet(self.parquet_yolu)
            birlesik = pd.concat([eski, yeni], ignore_index=True)
        else:
            birlesik = yeni
        birlesik.to_parquet(self.parquet_yolu, index=False)
        self.tampon.clear()
        self.son_yazma = ortak.simdi_ns()

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
        with open(self.meta_yolu, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    # -----------------------------------------------------------------
    # Ana döngü
    # -----------------------------------------------------------------
    def calistir(self) -> None:
        self.soketleri_ac()
        self.meta_baslat()
        ortak.log(f"Kayıt başladı: {self.ucus_id}. Durdurmak için Ctrl+C.", "BILGI")
        son_rapor = ortak.simdi_ns()

        while self.calisiyor:
            okunabilir, _, _ = select.select(
                [self.udp_sok, self.enjeksiyon_sok, self.tcp_sok], [], [], 0.5
            )
            for sok in okunabilir:
                if sok is self.udp_sok:
                    try:
                        veri, adres = self.udp_sok.recvfrom(65535)
                    except BlockingIOError:
                        continue
                    if not veri:
                        continue
                    self.gcs_adresleri.add(adres)
                    # gcs2uav: SITL'ye ilet
                    try:
                        self.tcp_sok.sendall(veri)
                    except OSError as e:
                        ortak.log(f"SITL'ye iletim hatası: {e}", "UYARI")
                    self._paketleri_coz(
                        self._mav_gcs, veri, "gcs2uav", adres[0], adres[1]
                    )
                elif sok is self.enjeksiyon_sok:
                    try:
                        veri, adres = self.enjeksiyon_sok.recvfrom(65535)
                    except BlockingIOError:
                        continue
                    if veri:
                        self.enjeksiyonu_isle(veri, adres)
                elif sok is self.tcp_sok:
                    try:
                        veri = self.tcp_sok.recv(65535)
                    except BlockingIOError:
                        continue
                    if not veri:
                        ortak.log("SITL bağlantısı kapandı.", "UYARI")
                        self.calisiyor = False
                        break
                    # uav2gcs: 14550'ye yazan herkese geri yolla
                    for adres in list(self.gcs_adresleri):
                        try:
                            self.udp_sok.sendto(veri, adres)
                        except OSError:
                            pass
                    self._dinleyenlere_gonder(veri)
                    # Otopilot adresini src olarak yaz
                    self._paketleri_coz(
                        self._mav_uav, veri, "uav2gcs", self.host, self.tcp_port
                    )

            # Periyodik tampon kontrolü (trafik yoksa da yazsın)
            simdi = ortak.simdi_ns()
            if (simdi - self.son_yazma) / 1e9 >= TAMPON_SURE_ESIGI and self.tampon:
                self.tamponu_yaz()
            # Her ~5 sn'de bir hız raporu
            if (simdi - son_rapor) / 1e9 >= 5.0:
                hiz = self.toplam_paket / max((simdi - self.baslangic_ns) / 1e9, 1e-9)
                ortak.log(
                    f"Toplam {self.toplam_paket} paket (~{hiz:.1f} paket/sn).",
                    "BILGI",
                )
                son_rapor = simdi

        self.kapat()

    def kapat(self) -> None:
        ortak.log("Kapanıyor; kalan tampon yazılıyor...", "BILGI")
        self.tamponu_yaz()
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


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--ucus",
        help="Uçuş adı (ör. F101_normal). Verilmezse config aralığından "
        "sonraki normal numara otomatik üretilir.",
    )
    args = ap.parse_args()

    if pd is None:
        ortak.log("pandas/pyarrow kurulu değil; parquet yazılamaz. setup.sh çalıştırın.", "UYARI")
    if mavutil is None:
        ortak.log("pymavlink kurulu değil; paketler çözümlenemez. setup.sh çalıştırın.", "UYARI")

    cfg = ortak.config_oku()
    ucus_id = args.ucus or ortak.sonraki_ucus_id("normal", cfg)
    # Çakışma koruması: numara bu cihazın aralığında mı, daha önce kullanıldı mı?
    ortak.ucus_id_dogrula(ucus_id, cfg, yeni_kayit=True)

    proxy = KayitProxy(ucus_id, cfg)

    def _sinyal(imza, cerceve):  # noqa: ANN001, ARG001
        proxy.calisiyor = False

    signal.signal(signal.SIGINT, _sinyal)
    signal.signal(signal.SIGTERM, _sinyal)

    proxy.calistir()
    return 0


if __name__ == "__main__":
    sys.exit(main())
