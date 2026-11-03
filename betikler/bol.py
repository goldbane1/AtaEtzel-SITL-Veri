#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bol.py — Uçuşları egitim/dogrulama/test olarak böler.

Tüm uçuşları UÇUŞ DÜZEYİNDE böler (bir uçuş tek bir kümede kalır; aynı
uçuşın pencereleri farklı kümelere dağılmaz -> veri sızıntısı önlenir) ve
veri/bolme.csv dosyasına (flight_id, split) yazar.

  - Varsayılan oranlar ~ %60 / %20 / %20 (egitim/dogrulama/test).
  - Saldırı türüne göre KATMANLAMA denenir: her tür mümkünse test'te de
    bulunsun. Yeterli uçuş yoksa Türkçe uyarı verilir.
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

    # Uçuşları türe göre grupla
    turler: dict[str, list[str]] = {}
    for ad in sorted(os.listdir(kok)):
        if (kok / ad).is_dir():
            tur = _ucus_turu(ad, kok / ad)
            turler.setdefault(tur, []).append(ad)

    if not turler:
        ortak.hata_ve_cik("Bölünecek uçuş bulunamadı.")

    rng = random.Random(args.tohum)
    atama: list[tuple[str, str]] = []

    for tur, ucuslar in turler.items():
        ucuslar = ucuslar[:]
        rng.shuffle(ucuslar)
        n = len(ucuslar)
        if n < 3:
            ortak.log(
                f"'{tur}' türünde yalnızca {n} uçuş var; katmanlama zayıf "
                "olabilir (her kümede bulunmayabilir).", "UYARI",
            )
        n_egitim = max(int(round(n * args.egitim)), 0)
        n_dogrulama = max(int(round(n * args.dogrulama)), 0)
        # kalan -> test
        for i, u in enumerate(ucuslar):
            if i < n_egitim:
                atama.append((u, "egitim"))
            elif i < n_egitim + n_dogrulama:
                atama.append((u, "dogrulama"))
            else:
                atama.append((u, "test"))

    # bolme.csv yaz
    cikti = ortak.repo_koku() / "veri" / "bolme.csv"
    cikti.parent.mkdir(parents=True, exist_ok=True)
    atama.sort()
    with open(cikti, "w", encoding="utf-8") as f:
        f.write("flight_id,split\n")
        for u, s in atama:
            f.write(f"{u},{s}\n")

    ozet: dict[str, int] = {}
    for _, s in atama:
        ozet[s] = ozet.get(s, 0) + 1
    ortak.log(f"bolme.csv yazıldı: {cikti}", "TAMAM")
    ortak.log(f"Küme dağılımı: {ozet} (toplam {len(atama)} uçuş).", "BILGI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
