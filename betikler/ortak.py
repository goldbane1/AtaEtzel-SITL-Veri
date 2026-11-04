#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ortak.py — Tüm betiklerin paylaştığı yardımcı fonksiyonlar.

AtaEtzel SITL veri üretim hattında her betik buradaki yardımcıları
kullanır. Böylece config okuma, dosya yolu üretme, zaman damgası,
loglama ve GÜVENLİK KONTROLÜ tek yerde toplanır ve üç bilgisayarda da
aynı davranır.

En önemli fonksiyon ``localhost_dogrula``: saldırı betiklerinin yalnızca
127.0.0.1 hedefine bağlanmasını zorunlu kılar. Bu kontrol SİLİNMEMELİDİR;
betiklerin dış ağa çıkmasını engeller.
"""

from __future__ import annotations

import ipaddress
import os
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import yaml  # config.yaml okumak için
except ImportError:  # pragma: no cover - yalnızca kurulum eksikse
    yaml = None


# ---------------------------------------------------------------------
# Yol yardımcıları
# ---------------------------------------------------------------------
def repo_koku() -> Path:
    """Reponun kök dizinini döndürür (bu dosya betikler/ altında)."""
    return Path(__file__).resolve().parent.parent


def config_yolu() -> Path:
    """config.yaml dosyasının tam yolunu döndürür."""
    return repo_koku() / "config.yaml"


# ---------------------------------------------------------------------
# Loglama (basit, Türkçe, zaman damgalı)
# ---------------------------------------------------------------------
def log(mesaj: str, seviye: str = "BILGI") -> None:
    """Ekrana Türkçe, zaman damgalı bir log satırı basar.

    seviye: BILGI, UYARI, HATA, TAMAM gibi kısa bir etiket.
    """
    saat = datetime.now().strftime("%H:%M:%S")
    print(f"[{saat}] [{seviye}] {mesaj}", flush=True)


def hata_ve_cik(mesaj: str, kod: int = 1) -> "None":
    """Türkçe hata basıp programı verilen çıkış koduyla sonlandırır."""
    log(mesaj, "HATA")
    sys.exit(kod)


# ---------------------------------------------------------------------
# Config okuma
# ---------------------------------------------------------------------
def config_oku() -> dict:
    """config.yaml'ı okur ve sözlük olarak döndürür.

    Eksik dosya veya eksik PyYAML durumunda Türkçe hata verir.
    """
    if yaml is None:
        hata_ve_cik(
            "PyYAML kurulu değil. Sanal ortamı etkinleştirip "
            "'pip install pyyaml' çalıştırın (veya setup.sh)."
        )
    yol = config_yolu()
    if not yol.exists():
        hata_ve_cik(f"config.yaml bulunamadı: {yol}")
    with open(yol, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        hata_ve_cik("config.yaml beklenen biçimde değil (sözlük bekleniyordu).")
    return cfg


# ---------------------------------------------------------------------
# GÜVENLİK: yalnızca localhost
# ---------------------------------------------------------------------
def localhost_mu(adres: str) -> bool:
    """Verilen adresin localhost (127.0.0.0/8 veya ::1) olup olmadığını döndürür."""
    try:
        ip = ipaddress.ip_address(adres)
    except ValueError:
        # Adı çözümlemeyi dene (ör. "localhost")
        try:
            cozulen = socket.gethostbyname(adres)
            ip = ipaddress.ip_address(cozulen)
        except Exception:
            return False
    return ip.is_loopback


def localhost_dogrula(adres: str) -> None:
    """GÜVENLİK KONTROLÜ — hedef localhost değilse Türkçe hata verip ÇIKAR.

    Tüm saldırı betikleri bir sokete bağlanmadan ÖNCE bunu çağırmalıdır.
    Bu betikler yalnızca kendi simülasyonumuz (127.0.0.1) içindir;
    gerçek sistemlere veya dış ağa ASLA yönlendirilemez.

    Bu fonksiyonu SİLMEYİN veya devre dışı bırakmayın.
    """
    if not localhost_mu(adres):
        hata_ve_cik(
            "GÜVENLİK: Saldırı betikleri yalnızca 127.0.0.1 (localhost) "
            f"hedefine bağlanabilir. Verilen hedef: '{adres}'. "
            "Bu betikler yalnızca kendi simülasyonumuz içindir; dış ağa "
            "çıkamaz. İşlem iptal edildi."
        )
    log(f"Güvenlik kontrolü geçildi: hedef {adres} (localhost).", "TAMAM")


# ---------------------------------------------------------------------
# Zaman damgası
# ---------------------------------------------------------------------
def simdi_ns() -> int:
    """Şu anki zamanı nanosaniye cinsinden döndürür (time.time_ns())."""
    return time.time_ns()


# ---------------------------------------------------------------------
# Uçuş klasörü ve numara yardımcıları
# ---------------------------------------------------------------------
def ucus_klasoru(ucus_id: str, cfg: dict | None = None) -> Path:
    """Bir uçuşın klasör yolunu (veri/ucuslar/<ucus_id>/) döndürür."""
    if cfg is None:
        cfg = config_oku()
    kok = repo_koku() / cfg.get("veri_klasoru", "veri/ucuslar")
    return kok / ucus_id


def ucus_klasoru_hazirla(ucus_id: str, cfg: dict | None = None) -> Path:
    """Uçuş klasörünü (ve ham/ alt klasörünü) oluşturur, yolunu döndürür."""
    klasor = ucus_klasoru(ucus_id, cfg)
    (klasor / "ham").mkdir(parents=True, exist_ok=True)
    return klasor


def _mevcut_numaralar(cfg: dict) -> list[int]:
    """veri/ucuslar altındaki FXXX_* klasörlerinden uçuş numaralarını toplar."""
    kok = repo_koku() / cfg.get("veri_klasoru", "veri/ucuslar")
    numaralar: list[int] = []
    if not kok.exists():
        return numaralar
    for ad in os.listdir(kok):
        # Beklenen biçim: F<numara>_<ad>, ör. F101_normal
        if ad.startswith("F") and "_" in ad:
            sayi_kismi = ad[1:].split("_", 1)[0]
            if sayi_kismi.isdigit():
                numaralar.append(int(sayi_kismi))
    return numaralar


def sonraki_ucus_no(cfg: dict | None = None) -> int:
    """config'teki aralıkta kullanılmamış bir SONRAKİ uçuş numarası üretir.

    O aralıktaki en büyük mevcut numaradan bir fazlasını döndürür; hiç
    uçuş yoksa aralığın başından başlar. Aralık dolmuşsa Türkçe hata verir.
    """
    if cfg is None:
        cfg = config_oku()
    aralik = cfg.get("ucus_no_araligi", [100, 199])
    alt, ust = int(aralik[0]), int(aralik[1])
    mevcut = [n for n in _mevcut_numaralar(cfg) if alt <= n <= ust]
    if not mevcut:
        return alt
    sonraki = max(mevcut) + 1
    if sonraki > ust:
        hata_ve_cik(
            f"Uçuş numarası aralığı doldu ({alt}-{ust}). "
            "config.yaml'daki aralığı kontrol edin veya eski uçuşları taşıyın."
        )
    return sonraki


def sonraki_ucus_id(ad_son_eki: str = "normal", cfg: dict | None = None) -> str:
    """Otomatik bir uçuş kimliği üretir, ör. 'F101_normal'."""
    if cfg is None:
        cfg = config_oku()
    no = sonraki_ucus_no(cfg)
    return f"F{no}_{ad_son_eki}"


# ---------------------------------------------------------------------
# Uçuş numarası ÇAKIŞMA KORUMASI
# ---------------------------------------------------------------------
# Üç (veya daha fazla) cihaz aynı anda üretim yapar. Veriler sonunda tek
# bir klasörde birleştirileceği için iki cihazın aynı uçuş adını (ör.
# F101_normal) üretmesi, birleştirmede bir uçuşun diğerinin ÜZERİNE
# yazılması demektir. Aşağıdaki kontroller bunu üretim ANINDA yakalar.
# Ayrıntılı anlatım: belgeler/UCUS_NUMARALARI.md

# Geçerli uçuş türleri (uçuş adının "_" sonrası kısmı).
UCUS_TURLERI = ("normal", "spoof_cmd", "impersonation", "replay", "flood", "fake_telemetry")

_REHBER = "Ayrıntı: belgeler/UCUS_NUMARALARI.md"


def ucus_id_coz(ucus_id: str) -> tuple[int, str] | None:
    """'F123_spoof_cmd' -> (123, 'spoof_cmd'). Biçim bozuksa None döndürür."""
    if not ucus_id.startswith("F") or "_" not in ucus_id:
        return None
    sayi, tur = ucus_id[1:].split("_", 1)
    if not sayi.isdigit() or not tur:
        return None
    return int(sayi), tur


def pc_blogu(pc_id: str) -> tuple[int, int] | None:
    """pc_id'ye ait yüzlük blok: 'pc1' -> (100, 199), 'pc2' -> (200, 299)."""
    if pc_id and pc_id.startswith("pc") and pc_id[2:].isdigit():
        n = int(pc_id[2:])
        if n >= 1:
            return n * 100, n * 100 + 99
    return None


def config_aralik_dogrula(cfg: dict) -> tuple[int, int]:
    """config.yaml'daki ucus_no_araligi'nın pc_id ile uyumlu olduğunu denetler.

    Örn. pc_id=pc2 ise aralık 200-299 bloğunun İÇİNDE olmalıdır (tamamı ya da
    bir parçası; aynı kişinin iki cihazı bloğu bölüşebilir). Sorun varsa
    Türkçe hata verip çıkar; yoksa (alt, ust) döndürür.
    """
    pc_id = str(cfg.get("pc_id", ""))
    blok = pc_blogu(pc_id)
    if blok is None:
        hata_ve_cik(
            f"config.yaml'daki pc_id geçersiz: '{pc_id}'. pc1, pc2 veya pc3 olmalı. {_REHBER}"
        )
    try:
        alt, ust = (int(x) for x in cfg.get("ucus_no_araligi", []))
    except (TypeError, ValueError):
        hata_ve_cik(
            "config.yaml'daki ucus_no_araligi '[alt, ust]' biçiminde olmalı "
            f"(ör. [{blok[0]}, {blok[1]}]). {_REHBER}"
        )
    if not (blok[0] <= alt <= ust <= blok[1]):
        hata_ve_cik(
            f"config.yaml uyumsuz: pc_id={pc_id} ama ucus_no_araligi=[{alt}, {ust}]. "
            f"{pc_id} için aralık {blok[0]}-{blok[1]} bloğunun içinde olmalı "
            f"(ör. [{blok[0]}, {blok[1]}]). Muhtemelen pc_id'yi değiştirip aralığı "
            f"değiştirmeyi unuttunuz. {_REHBER}"
        )
    return alt, ust


def ucus_id_dogrula(
    ucus_id: str,
    cfg: dict | None = None,
    yeni_kayit: bool = False,
    beklenen_tur: str | None = None,
) -> None:
    """Uçuş adının bu cihaza uygun olduğunu denetler; değilse Türkçe hata verip ÇIKAR.

    Kontroller:
      1. Biçim: F<numara>_<tür> (ör. F101_normal, F205_spoof_cmd).
      2. Tür: normal veya 5 saldırı türünden biri; beklenen_tur verilmişse ona eşit.
      3. Numara: config.yaml'daki ucus_no_araligi içinde (başka cihazın
         numarasını kullanmayı engeller).
      4. yeni_kayit=True ise: bu numarada (türü ne olursa olsun) daha önce
         kayıt yapılmamış olmalı (eski uçuşun üzerine yazmayı engeller).
    """
    if cfg is None:
        cfg = config_oku()
    alt, ust = config_aralik_dogrula(cfg)
    kullanilan = [n for n in _mevcut_numaralar(cfg) if alt <= n <= ust]
    bos_no = max(kullanilan) + 1 if kullanilan else alt
    if bos_no > ust:
        oneri = f"UYARI: aralığınız (F{alt}-F{ust}) dolmuş, config.yaml'ı güncelleyin"
    else:
        oneri = f"Bu cihaz için sıradaki boş ad: F{bos_no}_{beklenen_tur or 'normal'}"

    cozum = ucus_id_coz(ucus_id)
    if cozum is None:
        hata_ve_cik(
            f"Uçuş adı geçersiz: '{ucus_id}'. Biçim F<numara>_<tür> olmalı "
            f"(ör. F{alt + 1}_normal). {oneri}. {_REHBER}"
        )
    no, tur = cozum

    if tur not in UCUS_TURLERI:
        hata_ve_cik(
            f"Uçuş türü geçersiz: '{tur}'. Geçerli türler: {', '.join(UCUS_TURLERI)}. {_REHBER}"
        )
    if beklenen_tur and tur != beklenen_tur:
        hata_ve_cik(
            f"Uçuş adı ile yapılan iş uyuşmuyor: ad '{ucus_id}' ama tür '{beklenen_tur}'. "
            f"Adın sonu '_{beklenen_tur}' olmalı (ör. F{no}_{beklenen_tur}). {_REHBER}"
        )

    if not (alt <= no <= ust):
        hata_ve_cik(
            f"F{no} bu cihazın numara aralığında DEĞİL. config.yaml: "
            f"pc_id={cfg.get('pc_id')}, ucus_no_araligi=[{alt}, {ust}]. "
            "Başka bir cihazın numarasını kullanırsanız veriler birleşirken "
            f"uçuşlar birbirinin üzerine yazılır. {oneri}. {_REHBER}"
        )

    if yeni_kayit:
        kok = repo_koku() / cfg.get("veri_klasoru", "veri/ucuslar")
        if kok.exists():
            for ad in sorted(os.listdir(kok)):
                mevcut = ucus_id_coz(ad)
                if mevcut is None or mevcut[0] != no:
                    continue
                klasor = kok / ad
                dolu = any(p.is_file() for p in klasor.rglob("*"))
                if ad == ucus_id and not dolu:
                    continue  # yarıda kalmış, içi boş klasör: güvenle kullanılabilir
                hata_ve_cik(
                    f"F{no} numarası zaten kullanılmış: veri/ucuslar/{ad}/ var. "
                    "Üzerine yazmamak için durduruldu. Yeni bir numara kullanın "
                    f"({oneri}). O uçuş hatalıysa ve silmek istiyorsanız: "
                    f"rm -rf veri/ucuslar/{ad}  {_REHBER}"
                )


# ---------------------------------------------------------------------
# Port yardımcısı
# ---------------------------------------------------------------------
def port_bos_mu(host: str, port: int) -> bool:
    """Verilen TCP portuna bağlanılamıyorsa (yani boşsa) True döndürür."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) != 0


# ---------------------------------------------------------------------
# ground_truth.json yardımcısı (saldırı betikleri için)
# ---------------------------------------------------------------------
def ground_truth_ekle(ucus_id: str, kayit: dict, cfg: dict | None = None) -> Path:
    """Bir saldırı kaydını uçuşın ground_truth.json'una EKLER (liste olarak).

    Aynı uçuşta birden fazla saldırı olabileceği için kayıtlar bir liste
    halinde tutulur. kayit şu alanları içermelidir: attack_type, start_ns,
    end_ns, attacker_addr, params.
    """
    if cfg is None:
        cfg = config_oku()
    import json
    klasor = ucus_klasoru_hazirla(ucus_id, cfg)
    yol = klasor / "ground_truth.json"
    if yol.exists():
        try:
            veri = json.loads(yol.read_text(encoding="utf-8"))
        except Exception:
            veri = {}
    else:
        veri = {}
    veri.setdefault("flight_id", ucus_id)
    veri.setdefault("attacks", [])
    veri["attacks"].append(kayit)
    yol.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"ground_truth.json güncellendi: {kayit.get('attack_type')} eklendi.", "TAMAM")
    return yol



if __name__ == "__main__":
    # Kullanım:
    #   python betikler/ortak.py                      -> config özeti + sıradaki uçuş
    #   python betikler/ortak.py --sonraki spoof_cmd  -> sıradaki boş adı yazar
    #   python betikler/ortak.py --kontrol F101_normal [--yeni] [--tur normal]
    #                                                 -> ad bu cihaza uygun mu?
    import argparse

    ap = argparse.ArgumentParser(description="Ortak yardımcılar / uçuş adı kontrolü.")
    ap.add_argument("--sonraki", metavar="TUR", choices=UCUS_TURLERI,
                    help="Bu tür için sıradaki boş uçuş adını yazdır.")
    ap.add_argument("--kontrol", metavar="UCUS_ID", help="Uçuş adını denetle.")
    ap.add_argument("--yeni", action="store_true",
                    help="--kontrol ile: bu numara daha önce kullanılmamış olmalı.")
    ap.add_argument("--tur", choices=UCUS_TURLERI,
                    help="--kontrol ile: adın sonu bu tür olmalı.")
    args = ap.parse_args()

    cfg = config_oku()
    if args.sonraki:
        config_aralik_dogrula(cfg)
        print(sonraki_ucus_id(args.sonraki, cfg))
    elif args.kontrol:
        ucus_id_dogrula(args.kontrol, cfg, yeni_kayit=args.yeni, beklenen_tur=args.tur)
        log(f"Uçuş adı uygun: {args.kontrol}", "TAMAM")
    else:
        alt, ust = config_aralik_dogrula(cfg)
        log(f"pc_id: {cfg.get('pc_id')}", "BILGI")
        log(f"uçuş aralığı: F{alt}-F{ust}", "BILGI")
        log(f"sonraki uçuş: {sonraki_ucus_id('normal', cfg)}", "BILGI")
        log("ortak.py kendini sınaması tamam.", "TAMAM")
