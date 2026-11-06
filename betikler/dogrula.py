#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dogrula.py — Uçuş klasörlerinin eksiksizliğini ve tutarlılığını kontrol eder.

Bir uçuş için şunları denetler ve Türkçe TAMAM/EKSİK raporlar:
  - paketler.parquet var mı ve boş değil mi
  - iki yön de (gcs2uav ve uav2gcs) mevcut mu
  - HEARTBEAT akıyor mu
  - meta.json var ve dolu mu
  - saldırılıysa: ground_truth.json var mı ve etiketlerle tutarlı mı
    (saldırı aralığında gerçekten saldırı etiketli paket var mı)
  - pencereler çıkarıldıysa: uçuşun pencereleri kesintisiz ve süreyle uyumlu mu

Kullanım:
    python betikler/dogrula.py --ucus F106_spoof_cmd
    python betikler/dogrula.py --hepsi
"""

from __future__ import annotations

import argparse
import json
import os

import ortak

try:
    import pandas as pd
except ImportError:
    pd = None


PENCERE_NS = 1_000_000_000  # 1 saniye


def pencere_sorunlari(pencereler: "pd.DataFrame", paketler: "pd.DataFrame") -> list[str]:
    """Bir uçuşun pencerelerinin kesintisiz olup olmadığını denetler.

    RS-TCN düzenli zaman serisi bekler: ilk paketten son pakete kadar her
    saniye için tam bir pencere olmalıdır.
    """
    sorunlar: list[str] = []
    baslangiclar = pencereler["window_start_ns"].astype("int64").sort_values()
    farklar = baslangiclar.diff().dropna()
    bozuk = int((farklar != PENCERE_NS).sum())
    if bozuk:
        sorunlar.append(f"pencereler kesintili ({bozuk} yerde adım 1 sn değil)")

    t0 = int(paketler["t_ns"].min())
    beklenen = (int(paketler["t_ns"].max()) - t0) // PENCERE_NS + 1
    if len(pencereler) != beklenen:
        sorunlar.append(f"pencere sayısı {len(pencereler)}, beklenen {beklenen}")
    if int(baslangiclar.iloc[0]) != t0:
        sorunlar.append("ilk pencere ilk paketle başlamıyor")
    return sorunlar


def bir_ucus_dogrula(ucus_id: str, cfg: dict) -> bool:
    klasor = ortak.ucus_klasoru(ucus_id, cfg)
    sorunlar: list[str] = []

    parquet_yolu = klasor / "paketler.parquet"
    df = None
    if not parquet_yolu.exists():
        sorunlar.append("paketler.parquet yok")
    else:
        df = pd.read_parquet(parquet_yolu)
        if df.empty:
            sorunlar.append("paketler.parquet boş")
        else:
            yonler = set(df["direction"].unique())
            if "gcs2uav" not in yonler:
                sorunlar.append("gcs2uav yönü yok")
            if "uav2gcs" not in yonler:
                sorunlar.append("uav2gcs yönü yok")
            if "HEARTBEAT" not in set(df["msgname"].unique()):
                sorunlar.append("HEARTBEAT akmıyor")

    # meta.json
    meta_yolu = klasor / "meta.json"
    if not meta_yolu.exists():
        sorunlar.append("meta.json yok")
    else:
        try:
            meta = json.loads(meta_yolu.read_text(encoding="utf-8"))
            if not meta.get("flight_id"):
                sorunlar.append("meta.json: flight_id boş")
        except Exception:
            sorunlar.append("meta.json okunamıyor")

    # ground_truth tutarlılığı
    gt_yolu = klasor / "ground_truth.json"
    if gt_yolu.exists() and df is not None and not df.empty:
        try:
            gt = json.loads(gt_yolu.read_text(encoding="utf-8"))
        except Exception:
            gt = {}
        saldirilar = gt.get("attacks", [])
        if "label" not in df.columns:
            sorunlar.append("ground_truth var ama paketler etiketlenmemiş (label yok)")
        else:
            for s in saldirilar:
                tur = s.get("attack_type")
                bas, bit = int(s.get("start_ns", 0)), int(s.get("end_ns", 0))
                aralik_df = df[(df["t_ns"] >= bas) & (df["t_ns"] <= bit)]
                if aralik_df.empty or (aralik_df["label"] == tur).sum() == 0:
                    sorunlar.append(
                        f"'{tur}' saldırı aralığında etiketli paket yok"
                    )

    # Pencereler (oznitelik.py çalıştırıldıysa)
    pencere_yolu = ortak.repo_koku() / "veri" / "oznitelikler" / "pencereler.parquet"
    if df is not None and not df.empty and pencere_yolu.exists():
        pencereler = pd.read_parquet(pencere_yolu)
        pencereler = pencereler[pencereler["flight_id"] == ucus_id]
        if pencereler.empty:
            ortak.log(f"{ucus_id}: pencereler.parquet'te yok, pencere kontrolü atlandı.", "UYARI")
        else:
            sorunlar.extend(pencere_sorunlari(pencereler, df))

    if sorunlar:
        ortak.log(f"{ucus_id}: EKSİK -> " + "; ".join(sorunlar), "HATA")
        return False
    ortak.log(f"{ucus_id}: TAMAM", "TAMAM")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--ucus", help="Tek bir uçuşı doğrula.")
    g.add_argument("--hepsi", action="store_true", help="Tüm uçuşları doğrula.")
    args = ap.parse_args()

    if pd is None:
        ortak.hata_ve_cik("pandas/pyarrow kurulu değil. setup.sh çalıştırın.")

    cfg = ortak.config_oku()
    if args.ucus:
        ok = bir_ucus_dogrula(args.ucus, cfg)
        return 0 if ok else 1

    kok = ortak.repo_koku() / cfg.get("veri_klasoru", "veri/ucuslar")
    if not kok.exists():
        ortak.hata_ve_cik(f"Uçuş klasörü yok: {kok}")
    toplam, tamam = 0, 0
    for ad in sorted(os.listdir(kok)):
        if (kok / ad).is_dir():
            toplam += 1
            if bir_ucus_dogrula(ad, cfg):
                tamam += 1
    print("")
    ortak.log(f"Özet: {tamam}/{toplam} uçuş TAMAM.",
              "TAMAM" if tamam == toplam else "UYARI")
    return 0 if tamam == toplam else 1


if __name__ == "__main__":
    raise SystemExit(main())
