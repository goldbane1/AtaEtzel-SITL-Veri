#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""proxy_performans.py — SITL'siz proxy döngü gecikmesi ölçümü.

Sahte bir SITL (ayrı süreç) saniyede --hiz paket gönderir; gerçek proxy bunları işleyip
diske yazar. Bir döngü adımının süresi (paket okuma, iletme, çözme, kuyruğa alma) ölçülür.

Kullanım:
    python betikler/proxy_performans.py --sure 60 --hiz 500
"""

from __future__ import annotations

import argparse
import multiprocessing
import socket
import statistics
import tempfile
import time
from pathlib import Path

import kayit_proxy
import ortak
from pymavlink.dialects.v20 import ardupilotmega as mavlink2


def _sahte_sitl(sunucu: socket.socket, sure_s: float, hiz: int, sayac) -> None:
    """Bağlanan proxy'ye belirlenen hızda ATTITUDE paketi yollar."""
    baglanti, _ = sunucu.accept()
    uretici = mavlink2.MAVLink(None, 1, 1)
    bitis = time.perf_counter() + sure_s
    sonraki = time.perf_counter()
    aralik = 1.0 / hiz
    while time.perf_counter() < bitis:
        baglanti.sendall(uretici.attitude_encode(1, 0.1, 0.2, 0.3, 0.0, 0.0, 0.0).pack(uretici))
        sayac.value += 1
        sonraki += aralik
        bekle = sonraki - time.perf_counter()
        if bekle > 0:
            time.sleep(bekle)
    time.sleep(0.5)
    baglanti.close()


def olc(sure_s: float, hiz: int, klasor: Path) -> dict:
    """Ölçümü yapar; ortalama ve p99 gecikmeyi (ms) ve paket sayılarını döndürür."""
    sunucu = socket.socket()
    sunucu.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sunucu.bind(("127.0.0.1", 0))
    sunucu.listen(1)
    # spawn: proxy iş parçacıkları varken fork güvenli değildir.
    baglam = multiprocessing.get_context("spawn")
    sayac = baglam.Value("Q", 0)
    surec = baglam.Process(target=_sahte_sitl, args=(sunucu, sure_s, hiz, sayac))
    surec.start()

    cfg = {"veri_klasoru": str(klasor), "host": "127.0.0.1", "udp_port": 0,
           "hava_enjeksiyon_port": 0, "tcp_port": sunucu.getsockname()[1]}
    proxy = kayit_proxy.KayitProxy("F100_normal", cfg)
    proxy.dongu_sureleri_ns = []
    proxy.calistir()
    surec.join()
    sunucu.close()

    sureler_ms = sorted(s / 1e6 for s in proxy.dongu_sureleri_ns)
    return {
        "gonderilen": sayac.value,
        "kaydedilen": proxy.yazici.yazilan_paket,
        "adim": len(sureler_ms),
        "ortalama_ms": statistics.fmean(sureler_ms),
        "p99_ms": sureler_ms[int(len(sureler_ms) * 0.99) - 1],
        "maks_ms": sureler_ms[-1],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sure", type=float, default=60.0, help="Ölçüm süresi (sn).")
    ap.add_argument("--hiz", type=int, default=500, help="Saniyedeki paket sayısı.")
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as klasor:
        s = olc(args.sure, args.hiz, Path(klasor))
    ortak.log(
        f"gönderilen={s['gonderilen']} kaydedilen={s['kaydedilen']} adım={s['adim']} "
        f"ortalama={s['ortalama_ms']:.3f} ms p99={s['p99_ms']:.3f} ms "
        f"maks={s['maks_ms']:.3f} ms", "TAMAM",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
