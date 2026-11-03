#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""etiketle.py — Paketleri ground_truth'a göre etiketler.

Bir uçuşın paketler.parquet'ini ve (varsa) ground_truth.json'unu okur,
her pakete bir "label" ekler:
  - Paketin src_ip:src_port'u ground_truth'taki attacker_addr ile eşleşiyor
    VE t_ns, [start_ns, end_ns] aralığındaysa  -> label = attack_type
  - Aksi halde                                  -> label = "normal"
  - ground_truth.json yoksa                     -> tüm paketler "normal"

UYARI: src_ip / src_port burada YALNIZCA etiketleme için kullanılır.
Bunlar ASLA öznitelik değildir; modele verilirse veri sızıntısı olur.

Kullanım:
    python betikler/etiketle.py --ucus F106_spoof_cmd
    python betikler/etiketle.py --hepsi
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


def _ground_truth_oku(klasor) -> list[dict]:
    yol = klasor / "ground_truth.json"
    if not yol.exists():
        return []
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except Exception:
        return []
    return veri.get("attacks", [])


def bir_ucus_etiketle(ucus_id: str, cfg: dict) -> bool:
    klasor = ortak.ucus_klasoru(ucus_id, cfg)
    parquet_yolu = klasor / "paketler.parquet"
    if not parquet_yolu.exists():
        ortak.log(f"{ucus_id}: paketler.parquet yok, atlanıyor.", "UYARI")
        return False

    df = pd.read_parquet(parquet_yolu)
    df["label"] = "normal"

    saldirilar = _ground_truth_oku(klasor)
    if not saldirilar:
        ortak.log(f"{ucus_id}: ground_truth yok -> tüm paketler normal.", "BILGI")
    else:
        df["_addr"] = df["src_ip"].astype(str) + ":" + df["src_port"].astype(str)
        for s in saldirilar:
            addr = str(s.get("attacker_addr", ""))
            tur = s.get("attack_type", "normal")
            bas = int(s.get("start_ns", 0))
            bit = int(s.get("end_ns", 0))
            maske = (df["_addr"] == addr) & (df["t_ns"] >= bas) & (df["t_ns"] <= bit)
            df.loc[maske, "label"] = tur
            ortak.log(
                f"{ucus_id}: {tur} -> {int(maske.sum())} paket etiketlendi "
                f"(addr={addr}).", "BILGI",
            )
        df = df.drop(columns=["_addr"])

    df.to_parquet(parquet_yolu, index=False)
    dagilim = df["label"].value_counts().to_dict()
    ortak.log(f"{ucus_id}: etiketlendi. Dağılım: {dagilim}", "TAMAM")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--ucus", help="Tek bir uçuşı etiketle.")
    g.add_argument("--hepsi", action="store_true", help="Tüm uçuşları etiketle.")
    args = ap.parse_args()

    if pd is None:
        ortak.hata_ve_cik("pandas/pyarrow kurulu değil. setup.sh çalıştırın.")

    cfg = ortak.config_oku()
    if args.ucus:
        bir_ucus_etiketle(args.ucus, cfg)
    else:
        kok = ortak.repo_koku() / cfg.get("veri_klasoru", "veri/ucuslar")
        if not kok.exists():
            ortak.hata_ve_cik(f"Uçuş klasörü yok: {kok}")
        for ad in sorted(os.listdir(kok)):
            if (kok / ad).is_dir():
                bir_ucus_etiketle(ad, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
