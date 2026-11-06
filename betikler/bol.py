#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bol.py — Uçuşları egitim/dogrulama/test olarak böler.

Tüm uçuşları UÇUŞ DÜZEYİNDE böler (bir uçuş tek bir kümede kalır; aynı
uçuşın pencereleri farklı kümelere dağılmaz -> veri sızıntısı önlenir) ve
veri/bolme.csv dosyasına (flight_id, split) yazar.

  - Varsayılan oranlar ~ %60 / %20 / %20 (egitim/dogrulama/test).
  - Saldırı türü + kanal profiline göre KATMANLAMA denenir: her tür mümkünse
    test'te de bulunsun. Yeterli uçuş yoksa Türkçe uyarı verilir.
  - veri/bolmeler/ altına değerlendirme senaryolarını yazar: T1, T2, T3 ve her
    saldırı türü için T4_<tür>.
  - Tekrar üretilebilirlik için SABİT tohum (seed) kullanılır.

Uçuş türü, uçuş adının sonundaki etiketten (F101_normal -> normal,
F106_spoof_cmd -> spoof_cmd) veya ground_truth.json'dan çıkarılır.

Kullanım:
    python betikler/bol.py
    python betikler/bol.py --egitim 0.6 --dogrulama 0.2 --test 0.2 --tohum 42
"""

from __future__ import annotations

import argparse
import json
import os
import random

import ortak

EGITIM_DISI_PROFIL = "agir"   # T3: Eğitim aralığı dışında kalan kanal profili


def _ucus_turu(ucus_id: str, klasor) -> str:
    """Uçuş türünü belirler (ground_truth varsa oradan, yoksa addan)."""
    gt = klasor / "ground_truth.json"
    if gt.exists():
        try:
            veri = json.loads(gt.read_text(encoding="utf-8"))
            saldirilar = veri.get("attacks", [])
            if saldirilar:
                return saldirilar[0].get("attack_type", "normal")
        except Exception:
            pass
    # addan: F106_spoof_cmd -> spoof_cmd
    if "_" in ucus_id:
        return ucus_id.split("_", 1)[1]
    return "normal"


def _kanal_profili(klasor) -> str:
    """Uçuşun kanal profili; meta.json'da yoksa temiz kabul edilir."""
    yol = klasor / "meta.json"
    if yol.exists():
        try:
            return (json.loads(yol.read_text(encoding="utf-8")).get("kanal") or {}).get(
                "profil", "temiz")
        except ValueError:
            pass
    return "temiz"


def katmanli_bol(ucuslar: dict[str, tuple[str, str]], egitim: float, dogrulama: float,
                 tohum: int) -> dict[str, str]:
    """Uçuşları (tür, profil) katmanlarına göre böler; bir uçuş tek kümede kalır.

    ucuslar: uçuş adı -> (tür, kanal profili)
    """
    katmanlar: dict[tuple[str, str], list[str]] = {}
    for ucus, katman in sorted(ucuslar.items()):
        katmanlar.setdefault(katman, []).append(ucus)

    rng = random.Random(tohum)
    atama: dict[str, str] = {}
    for katman in sorted(katmanlar):
        liste = katmanlar[katman][:]
        rng.shuffle(liste)
        n = len(liste)
        if n < 3:
            ortak.log(f"{katman} katmanında yalnızca {n} uçuş var; katmanlama zayıf "
                      "olabilir (her kümede bulunmayabilir).", "UYARI")
        n_egitim = int(round(n * egitim))
        n_dogrulama = int(round(n * dogrulama))
        for i, ucus in enumerate(liste):
            if i < n_egitim:
                atama[ucus] = "egitim"
            elif i < n_egitim + n_dogrulama:
                atama[ucus] = "dogrulama"
            else:
                atama[ucus] = "test"
    return atama


def senaryo_bolmeleri(atama: dict[str, str],
                      ucuslar: dict[str, tuple[str, str]]) -> dict[str, dict[str, str]]:
    """Değerlendirme senaryolarının bölmelerini üretir (MIMARI.md 4. bölüm).

    Dosyada olmayan uçuş o senaryoda kullanılmaz. T5 dış veri setidir, burada yoktur.
    "agir" eğitim aralığının DIŞINDADIR: T1 ve T2 de onu eğitimde kullanmaz.
    """
    def profil(ucus):
        return ucuslar[ucus][1]

    egitim_araligi = {u: k for u, k in atama.items()
                      if k != "test" and profil(u) != EGITIM_DISI_PROFIL}
    senaryolar = {
        "T1": {**egitim_araligi,
               **{u: "test" for u, k in atama.items() if k == "test" and profil(u) == "temiz"}},
        "T2": {**egitim_araligi,
               **{u: "test" for u, k in atama.items()
                  if k == "test" and profil(u) in ("hafif", "orta")}},
        "T3": {**egitim_araligi,
               **{u: "test" for u in atama if profil(u) == EGITIM_DISI_PROFIL}},
    }
    for tur in sorted({t for t, _ in ucuslar.values()} - {"normal"}):
        senaryolar[f"T4_{tur}"] = {
            **{u: k for u, k in egitim_araligi.items() if ucuslar[u][0] != tur},
            **{u: "test" for u, k in atama.items()
               if (k == "test" and profil(u) != EGITIM_DISI_PROFIL) or ucuslar[u][0] == tur},
        }
    return senaryolar


def _csv_yaz(yol, atama: dict[str, str]) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        f.write("flight_id,split\n")
        for ucus, kume in sorted(atama.items()):
            f.write(f"{ucus},{kume}\n")


def senaryo_uyarilari(senaryolar: dict[str, dict[str, str]]) -> None:
    """Test kümesi boş kalan senaryoları Türkçe bildirir."""
    for ad, atama in senaryolar.items():
        if "test" not in atama.values():
            ortak.log(f"{ad}: test kümesi boş, yeterli uçuş yok.", "UYARI")
    if "T4_flood" not in senaryolar:
        ortak.log("Bazı saldırı türleri yok; T4 senaryoları eksik olabilir.", "UYARI")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--egitim", type=float, default=0.6, help="Eğitim oranı.")
    ap.add_argument("--dogrulama", type=float, default=0.2, help="Doğrulama oranı.")
    ap.add_argument("--test", type=float, default=0.2, help="Test oranı.")
    ap.add_argument("--tohum", type=int, default=42, help="Rastgelelik tohumu.")
    args = ap.parse_args()

    toplam_oran = args.egitim + args.dogrulama + args.test
    if abs(toplam_oran - 1.0) > 1e-6:
        ortak.hata_ve_cik(f"Oranların toplamı 1.0 olmalı; verilen: {toplam_oran}")

    cfg = ortak.config_oku()
    kok = ortak.repo_koku() / cfg.get("veri_klasoru", "veri/ucuslar")
    if not kok.exists():
        ortak.hata_ve_cik(f"Uçuş klasörü yok: {kok}")

    # Her uçuşun türü ve kanal profili
    ucuslar: dict[str, tuple[str, str]] = {}
    for ad in sorted(os.listdir(kok)):
        if (kok / ad).is_dir() and not ortak.ucus_basarisiz_mi(ad, cfg):
            ucuslar[ad] = (_ucus_turu(ad, kok / ad), _kanal_profili(kok / ad))

    if not ucuslar:
        ortak.hata_ve_cik("Bölünecek uçuş bulunamadı.")

    atama_sozluk = katmanli_bol(ucuslar, args.egitim, args.dogrulama, args.tohum)
    atama = sorted(atama_sozluk.items())

    # bolme.csv yaz
    cikti = ortak.repo_koku() / "veri" / "bolme.csv"
    _csv_yaz(cikti, atama_sozluk)

    # Senaryo bölmeleri
    senaryolar = senaryo_bolmeleri(atama_sozluk, ucuslar)
    for ad, senaryo in senaryolar.items():
        _csv_yaz(ortak.repo_koku() / "veri" / "bolmeler" / f"{ad}.csv", senaryo)
    senaryo_uyarilari(senaryolar)
    ortak.log(f"{len(senaryolar)} senaryo bölmesi -> veri/bolmeler/", "TAMAM")

    ozet: dict[str, int] = {}
    for _, s in atama:
        ozet[s] = ozet.get(s, 0) + 1
    ortak.log(f"bolme.csv yazıldı: {cikti}", "TAMAM")
    ortak.log(f"Küme dağılımı: {ozet} (toplam {len(atama)} uçuş).", "BILGI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
