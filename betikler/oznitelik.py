#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""oznitelik.py — 1 saniyelik öznitelik pencereleri çıkarır.

Etiketli paketleri okur, 1 saniyelik pencerelere böler ve her pencere için
VERI_SEMASI.md'deki öznitelik sütunlarını hesaplar. Çıktı:
    veri/oznitelikler/pencereler.parquet

Öznitelikler (pencere başına):
  - flight_id, window_start_ns
  - toplam paket sayısı
  - mesaj türüne göre sayılar (ilgili önemli türler için sütunlar)
  - farklı sysid sayısı
  - seq atlama ve seq tekrar sayısı
  - paketler arası sürenin ortalaması ve std'si
  - komut mesajı sayısı
  - label (pencerede en az bir saldırı paketi varsa o tür, yoksa normal)
  - attack_ratio (penceredeki saldırı paketi oranı)

KRİTİK: src_ip, src_port, raw_hex KESİNLİKLE öznitelik olmaz (veri sızıntısı).

Kullanım:
    python betikler/oznitelik.py --ucus F106_spoof_cmd
    python betikler/oznitelik.py --hepsi
"""

from __future__ import annotations

import argparse
import os

import numpy as np
import ortak

try:
    import pandas as pd
except ImportError:
    pd = None

PENCERE_NS = 1_000_000_000  # 1 saniye

# Pencere başına sayılacak önemli mesaj türleri (sütun olurlar: n_<ad>).
SAYILACAK_MSGLER = [
    "HEARTBEAT", "COMMAND_LONG", "COMMAND_INT", "GLOBAL_POSITION_INT",
    "ATTITUDE", "RC_CHANNELS", "SYS_STATUS", "PING", "MISSION_ITEM",
    "PARAM_SET", "SET_MODE",
]
# "komut mesajı" sayılan türler
KOMUT_TURLERI = {"COMMAND_LONG", "COMMAND_INT", "SET_MODE", "MISSION_ITEM",
                 "MISSION_SET_CURRENT", "PARAM_SET", "RC_CHANNELS_OVERRIDE"}


def _pencere_oznitelikleri(grup: "pd.DataFrame", flight_id: str,
                           pencere_baslangic: int) -> dict:
    grup = grup.sort_values("t_ns")
    toplam = len(grup)

    # seq atlama/tekrar (yöne göre ayrı bakılır)
    seq_atlama = 0
    seq_tekrar = 0
    for _, yon_grubu in grup.groupby("direction"):
        seqler = yon_grubu["seq"].to_numpy()
        if len(seqler) >= 2:
            farklar = (np.diff(seqler.astype(int)) % 256)
            seq_atlama += int(np.sum(farklar > 1))
            seq_tekrar += int(np.sum(farklar == 0))

    # paketler arası süre (ns -> s)
    tler = grup["t_ns"].to_numpy().astype(np.float64)
    if len(tler) >= 2:
        aralar = np.diff(tler) / 1e9
        ara_ort = float(np.mean(aralar))
        ara_std = float(np.std(aralar))
    else:
        ara_ort = 0.0
        ara_std = 0.0

    satir = {
        "flight_id": flight_id,
        "window_start_ns": int(pencere_baslangic),
        "toplam_paket": toplam,
        "farkli_sysid": int(grup["sysid"].nunique()),
        "seq_atlama": seq_atlama,
        "seq_tekrar": seq_tekrar,
        "paket_arasi_ort_s": ara_ort,
        "paket_arasi_std_s": ara_std,
        "komut_sayisi": int(grup["msgname"].isin(KOMUT_TURLERI).sum()),
    }
    # mesaj türü sayıları
    sayim = grup["msgname"].value_counts().to_dict()
    for m in SAYILACAK_MSGLER:
        satir[f"n_{m}"] = int(sayim.get(m, 0))

    # etiket ve attack_ratio
    if "label" in grup.columns:
        saldiri_maske = grup["label"] != "normal"
        n_saldiri = int(saldiri_maske.sum())
        satir["attack_ratio"] = round(n_saldiri / toplam, 4) if toplam else 0.0
        if n_saldiri > 0:
            # Penceredeki baskın saldırı türü
            satir["label"] = grup.loc[saldiri_maske, "label"].mode().iloc[0]
        else:
            satir["label"] = "normal"
    else:
        satir["attack_ratio"] = 0.0
        satir["label"] = "normal"
    return satir


def bir_ucus_oznitelik(ucus_id: str, cfg: dict) -> "pd.DataFrame | None":
    klasor = ortak.ucus_klasoru(ucus_id, cfg)
    parquet_yolu = klasor / "paketler.parquet"
    if not parquet_yolu.exists():
        ortak.log(f"{ucus_id}: paketler.parquet yok, atlanıyor.", "UYARI")
        return None
    df = pd.read_parquet(parquet_yolu)
    if df.empty:
        ortak.log(f"{ucus_id}: paketler boş, atlanıyor.", "UYARI")
        return None
    if "label" not in df.columns:
        ortak.log(f"{ucus_id}: label yok; önce etiketle.py çalıştırın.", "UYARI")

    t0 = int(df["t_ns"].min())
    df["_pencere"] = ((df["t_ns"].astype("int64") - t0) // PENCERE_NS)

    satirlar = []
    for pencere_no, grup in df.groupby("_pencere"):
        pencere_baslangic = t0 + int(pencere_no) * PENCERE_NS
        satirlar.append(_pencere_oznitelikleri(grup, ucus_id, pencere_baslangic))
    sonuc = pd.DataFrame(satirlar)
    ortak.log(f"{ucus_id}: {len(sonuc)} pencere çıkarıldı.", "TAMAM")
    return sonuc


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--ucus", help="Tek bir uçuş için öznitelik çıkar.")
    g.add_argument("--hepsi", action="store_true", help="Tüm uçuşlar için çıkar.")
    args = ap.parse_args()

    if pd is None:
        ortak.hata_ve_cik("pandas/pyarrow kurulu değil. setup.sh çalıştırın.")

    cfg = ortak.config_oku()
    parcalar = []
    if args.ucus:
        d = bir_ucus_oznitelik(args.ucus, cfg)
        if d is not None:
            parcalar.append(d)
    else:
        kok = ortak.repo_koku() / cfg.get("veri_klasoru", "veri/ucuslar")
        if not kok.exists():
            ortak.hata_ve_cik(f"Uçuş klasörü yok: {kok}")
        for ad in sorted(os.listdir(kok)):
            if (kok / ad).is_dir():
                d = bir_ucus_oznitelik(ad, cfg)
                if d is not None:
                    parcalar.append(d)

    if not parcalar:
        ortak.hata_ve_cik("Öznitelik çıkarılacak veri bulunamadı.")

    hepsi = pd.concat(parcalar, ignore_index=True)

    # GÜVENLİK: sızıntı sütunları asla bulunmamalı
    yasak = {"src_ip", "src_port", "raw_hex"}
    sizan = yasak.intersection(hepsi.columns)
    if sizan:
        ortak.hata_ve_cik(f"Sızıntı sütunları öznitelikte bulundu: {sizan}")

    cikti_dizin = ortak.repo_koku() / "veri" / "oznitelikler"
    cikti_dizin.mkdir(parents=True, exist_ok=True)
    cikti = cikti_dizin / "pencereler.parquet"
    hepsi.to_parquet(cikti, index=False)
    ortak.log(f"Toplam {len(hepsi)} pencere -> {cikti}", "TAMAM")
    ortak.log(f"Etiket dağılımı: {hepsi['label'].value_counts().to_dict()}", "BILGI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
