#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""oznitelik.py — 1 saniyelik öznitelik pencereleri çıkarır.

Etiketli paketleri okur, 1 saniyelik pencerelere böler ve her pencere için
VERI_SEMASI.md'deki öznitelik sütunlarını hesaplar. Çıktı:
    veri/oznitelikler/pencereler.parquet

İlk paketten son pakete kadar HER saniye için bir pencere üretilir; boş saniyelerde
sayımlar 0 olur. Bir pencere yalnızca kendi bitişine kadarki veriyi kullanır.

Öznitelikler (pencere başına):
  - flight_id, window_start_ns
  - toplam ve yön başına paket sayısı, boş pencere bilgisi, son paketten beri geçen süre
  - mesaj türüne göre sayılar (toplam ve yön başına)
  - farklı sysid sayısı, kaynak başına seq atlama ve tekrar sayısı
  - paketler arası sürenin ortalaması ve std'si (toplam ve yön başına)
  - komut mesajı sayısı
  - komutu kim, nasıl gönderdi: yer istasyonu akış sayısı, sysid içi seq bozulması,
    komut tekrarı, kritik komut sayısı, en kısa komut aralığı
  - komut–yanıt tutarlılığı (komut_yanit.py, 10 sütun)

Etiket sütunları (modele girdi OLMAZ):
  - saldiri_araliginda, saldiri_turu_aralik (ground_truth aralığından)
  - label (pencerede en az bir saldırı paketi varsa o tür, yoksa normal)
  - attack_ratio (penceredeki saldırı paketi oranı)

KRİTİK: src_ip, src_port, raw_hex KESİNLİKLE öznitelik olmaz (veri sızıntısı).

Kullanım:
    python betikler/oznitelik.py --ucus F106_spoof_cmd
    python betikler/oznitelik.py --hepsi
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np
import komut_yanit
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
    "PARAM_SET", "SET_MODE", "COMMAND_ACK", "MISSION_COUNT", "MISSION_REQUEST",
    "MISSION_REQUEST_INT", "MISSION_ACK", "MISSION_CURRENT", "PARAM_VALUE",
]
# "komut mesajı" sayılan türler
KOMUT_TURLERI = {"COMMAND_LONG", "COMMAND_INT", "SET_MODE", "MISSION_ITEM",
                 "MISSION_SET_CURRENT", "PARAM_SET", "RC_CHANNELS_OVERRIDE"}

# Kritik komutlar (MAV_CMD): uçuşun gidişatını doğrudan değiştirenler.
KRITIK_KOMUTLAR = {
    20,   # NAV_RETURN_TO_LAUNCH
    21,   # NAV_LAND
    176,  # DO_SET_MODE
    185,  # DO_FLIGHTTERMINATION
    246,  # PREFLIGHT_REBOOT_SHUTDOWN
    300,  # MISSION_START
    400,  # COMPONENT_ARM_DISARM
}
SET_MODE_NO = -1              # SET_MODE'un COMMAND numarası yok; bu değer temsil eder
KOMUT_ARALIGI_UST_S = 60.0    # komut yoksa ya da aralık daha uzunsa kullanılan değer


def _komut_no(msgname: str, fields_json: str) -> float:
    """Bir gcs2uav mesajının komut numarasını döndürür; komut değilse NaN."""
    if msgname == "SET_MODE":
        return float(SET_MODE_NO)
    try:
        return float(json.loads(fields_json)["command"])
    except (TypeError, ValueError, KeyError):
        return float("nan")


def _paket_ozellikleri(df: "pd.DataFrame") -> "pd.DataFrame":
    """Pencere sınırından bağımsız, paket başına ön hesapları ekler.

    Hepsi yalnızca geçmiş paketlere bakar (shift ile bir önceki paket). Bu
    yüzden pencere sınırında akış kopmaz ve nedensellik bozulmaz.
    """
    df = df.sort_values("t_ns", kind="stable").reset_index(drop=True)

    # seq her kaynak (yön + sysid + compid) için ayrı işler.
    onceki = df.groupby(["direction", "sysid", "compid"], sort=False)["seq"].shift(1)
    fark = (df["seq"] - onceki) % 256
    df["_seq_atlama"] = fark > 1
    df["_seq_tekrar"] = fark == 0

    gcs = df["direction"] == "gcs2uav"
    df["_gcs_sysid_bozulma"] = False
    if gcs.any():
        # compid ayrımı YOK: sahte akış gerçek akışla aynı sysid'de karışırsa görünür.
        onceki_gcs = df[gcs].groupby("sysid", sort=False)["seq"].shift(1)
        fark_gcs = (df.loc[gcs, "seq"] - onceki_gcs) % 256
        df.loc[gcs, "_gcs_sysid_bozulma"] = fark_gcs.notna() & (fark_gcs != 1)

    # gcs2uav komutları: COMMAND_LONG, COMMAND_INT ve SET_MODE.
    komut = gcs & df["msgname"].isin(["COMMAND_LONG", "COMMAND_INT", "SET_MODE"])
    df["_komut_no"] = float("nan")
    df["_kritik"] = False
    df["_komut_araligi_s"] = float("nan")
    if komut.any():
        df.loc[komut, "_komut_no"] = [
            _komut_no(m, f) for m, f in zip(df.loc[komut, "msgname"], df.loc[komut, "fields_json"])
        ]
        df.loc[komut, "_kritik"] = (
            df.loc[komut, "_komut_no"].isin(KRITIK_KOMUTLAR)
            | (df.loc[komut, "_komut_no"] == SET_MODE_NO)
        )
        aralik = df.loc[komut, "t_ns"].astype("int64").diff() / 1e9
        df.loc[komut, "_komut_araligi_s"] = aralik.clip(upper=KOMUT_ARALIGI_UST_S)
    return df


def _yon_zamanlamasi(grup: "pd.DataFrame", yon: str) -> tuple[float, float]:
    """Bir yönün pencere içi paketler arası süre ortalaması ve std'si (sn)."""
    tler = grup.loc[grup["direction"] == yon, "t_ns"].to_numpy().astype(np.float64)
    if len(tler) < 2:
        return 0.0, 0.0
    aralar = np.diff(tler) / 1e9
    return float(np.mean(aralar)), float(np.std(aralar))


def _pencere_oznitelikleri(grup: "pd.DataFrame", flight_id: str,
                           pencere_baslangic: int) -> dict:
    """Bir pencerenin sütunlarını üretir. grup boş olabilir (boş pencere)."""
    toplam = len(grup)

    # paketler arası süre (ns -> s)
    tler = grup["t_ns"].to_numpy().astype(np.float64)
    if len(tler) >= 2:
        aralar = np.diff(tler) / 1e9
        ara_ort = float(np.mean(aralar))
        ara_std = float(np.std(aralar))
    else:
        ara_ort = 0.0
        ara_std = 0.0

    g2u = grup[grup["direction"] == "gcs2uav"]
    u2g = grup[grup["direction"] == "uav2gcs"]
    g2u_ort, g2u_std = _yon_zamanlamasi(grup, "gcs2uav")
    u2g_ort, u2g_std = _yon_zamanlamasi(grup, "uav2gcs")
    komutlar = grup["_komut_no"].dropna()

    satir = {
        "flight_id": flight_id,
        "window_start_ns": int(pencere_baslangic),
        "toplam_paket": toplam,
        "paket_gcs2uav": len(g2u),
        "paket_uav2gcs": len(u2g),
        "bos_pencere": int(toplam == 0),
        "farkli_sysid": int(grup["sysid"].nunique()),
        "seq_atlama": int(grup["_seq_atlama"].sum()),
        "seq_tekrar": int(grup["_seq_tekrar"].sum()),
        "paket_arasi_ort_s": ara_ort,
        "paket_arasi_std_s": ara_std,
        "paket_arasi_ort_s_g2u": g2u_ort,
        "paket_arasi_std_s_g2u": g2u_std,
        "paket_arasi_ort_s_u2g": u2g_ort,
        "paket_arasi_std_s_u2g": u2g_std,
        "komut_sayisi": int(grup["msgname"].isin(KOMUT_TURLERI).sum()),
        "gcs_akis_sayisi": len(g2u[["sysid", "compid"]].drop_duplicates()),
        "gcs_sysid_seq_bozulma": int(grup["_gcs_sysid_bozulma"].sum()),
        "ayni_komut_tekrari": int(len(komutlar) - komutlar.nunique()),
        "kritik_komut_sayisi": int(grup["_kritik"].sum()),
        "komut_araligi_min_s": float(
            grup["_komut_araligi_s"].min() if grup["_komut_araligi_s"].notna().any()
            else KOMUT_ARALIGI_UST_S
        ),
    }
    # mesaj türü sayıları: toplam ve yön başına
    sayim = grup["msgname"].value_counts().to_dict()
    sayim_g2u = g2u["msgname"].value_counts().to_dict()
    sayim_u2g = u2g["msgname"].value_counts().to_dict()
    for m in SAYILACAK_MSGLER:
        satir[f"n_{m}"] = int(sayim.get(m, 0))
        satir[f"n_g2u_{m}"] = int(sayim_g2u.get(m, 0))
        satir[f"n_u2g_{m}"] = int(sayim_u2g.get(m, 0))

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


def _ground_truth_oku(klasor) -> list[dict]:
    """Uçuşun saldırı kayıtlarını okur; dosya yoksa ya da bozuksa boş liste."""
    yol = klasor / "ground_truth.json"
    if not yol.exists():
        return []
    try:
        return json.loads(yol.read_text(encoding="utf-8")).get("attacks", [])
    except (OSError, ValueError):
        return []


def _saldiri_turu_aralik(bas_ns: int, bit_ns: int, saldirilar: list[dict]) -> str:
    """Pencereyle en çok örtüşen saldırının türü; örtüşme yoksa 'normal'.

    UYARI: Bu bilgi ground truth'tan gelir, ETİKETTİR. Modele girdi olarak
    verilmez; değerlendirme ve tespit gecikmesi ölçümü içindir.
    """
    en_iyi, en_iyi_ortusme = "normal", 0
    for saldiri in saldirilar:
        ortusme = (min(bit_ns, int(saldiri.get("end_ns", 0)) + 1)
                   - max(bas_ns, int(saldiri.get("start_ns", 0))))
        if ortusme > en_iyi_ortusme:
            en_iyi, en_iyi_ortusme = str(saldiri.get("attack_type", "normal")), ortusme
    return en_iyi


def pencere_tablosu(df: "pd.DataFrame", ucus_id: str,
                    saldirilar: list[dict] | None = None) -> "pd.DataFrame":
    """Paket tablosundan kesintisiz 1 sn'lik pencere tablosunu üretir.

    İlk paketten son pakete kadar HER saniye için bir satır vardır: RS-TCN
    düzenli zaman serisi bekler, boş saniye de bilgidir.
    """
    saldirilar = saldirilar or []
    df = _paket_ozellikleri(df)
    t0 = int(df["t_ns"].min())
    df["_pencere"] = (df["t_ns"].astype("int64") - t0) // PENCERE_NS
    pencere_sayisi = int(df["_pencere"].max()) + 1

    gruplar = {int(no): grup for no, grup in df.groupby("_pencere")}
    bos_grup = df.iloc[0:0]
    satirlar = []
    son_paket_ns = t0
    for pencere_no in range(pencere_sayisi):
        grup = gruplar.get(pencere_no, bos_grup)
        bas_ns = t0 + pencere_no * PENCERE_NS
        bit_ns = bas_ns + PENCERE_NS
        satir = _pencere_oznitelikleri(grup, ucus_id, bas_ns)
        if len(grup):
            son_paket_ns = int(grup["t_ns"].max())
        satir["son_paketten_beri_s"] = (bit_ns - son_paket_ns) / 1e9
        tur = _saldiri_turu_aralik(bas_ns, bit_ns, saldirilar)
        satir["saldiri_araliginda"] = int(tur != "normal")
        satir["saldiri_turu_aralik"] = tur
        satirlar.append(satir)
    sonuc = pd.DataFrame(satirlar)

    komut_yanit_df = komut_yanit.komut_yanit_oznitelikleri(df, t0, PENCERE_NS)
    for sutun in komut_yanit.SUTUNLAR:
        sonuc[sutun] = komut_yanit_df[sutun].to_numpy()

    # Sözleşme: etiket sütunları en sonda kalır (VERI_SEMASI.md).
    son_sutunlar = ["saldiri_araliginda", "saldiri_turu_aralik", "attack_ratio", "label"]
    return sonuc[[s for s in sonuc.columns if s not in son_sutunlar] + son_sutunlar]


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

    sonuc = pencere_tablosu(df, ucus_id, _ground_truth_oku(klasor))
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
                if ortak.ucus_basarisiz_mi(ad, cfg):
                    ortak.log(f"{ad}: başarısız uçuş, atlanıyor.", "UYARI")
                    continue
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
