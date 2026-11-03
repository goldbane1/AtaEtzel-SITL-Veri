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
    # Hızlı kendini sınama: config'i oku ve özetle.
    cfg = config_oku()
    log(f"pc_id: {cfg.get('pc_id')}", "BILGI")
    log(f"uçuş aralığı: {cfg.get('ucus_no_araligi')}", "BILGI")
    log(f"sonraki uçuş: {sonraki_ucus_id('normal', cfg)}", "BILGI")
    log("ortak.py kendini sınaması tamam.", "TAMAM")
