#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kanal.py — Telsiz kanalı bozulması (gecikme, titreşim, paket kaybı).

Gerçek telsiz kanalı temiz değildir. Model yalnızca kusursuz kanalda eğitilirse
gerçek gecikme ve kaybı saldırı sanar. Bozulma netem yerine proxy içinde yapılır:
tohumlu olduğu için tekrar üretilebilir, her makinede aynı çalışır.

Bozulma güvenlik duvarının konumuna göre uygulanır (MIMARI.md 5. bölüm):
  gcs2uav: Paket telsizden geçtikten sonra duvara ulaşır. Bozulma kayıttan ÖNCEDİR;
           kaybolan paket kaydedilmez ve iletilmez.
  uav2gcs: Paket duvardan çıktıktan sonra telsize girer. Bozulma kayıttan SONRADIR;
           kaybolan paket kayıtta durur ama yer istasyonuna ulaşmaz.

Gönderim bloklamaz: Paketler zamanı gelene kadar kuyrukta bekler, proxy döngüsü
her turda zamanı gelenleri gönderir. Aynı yönde sıra bozulmaz.
"""

from __future__ import annotations

import heapq
import itertools
import random
import time
from dataclasses import dataclass
from typing import Callable

GCS2UAV = "gcs2uav"
UAV2GCS = "uav2gcs"


@dataclass(frozen=True)
class KanalAyari:
    profil: str = "temiz"
    gecikme_ms: float = 0.0
    jitter_ms: float = 0.0
    kayip_yuzde: float = 0.0
    tohum: int = 0

    @property
    def temiz(self) -> bool:
        return self.gecikme_ms == 0 and self.jitter_ms == 0 and self.kayip_yuzde == 0


class Kanal:
    """Paketleri bozarak zamanlayan kanal. Yön başına ayrı rastgele akış kullanır."""

    def __init__(self, ayar: KanalAyari | None = None,
                 saat: Callable[[], float] = time.monotonic) -> None:
        self.ayar = ayar or KanalAyari()
        self.saat = saat
        self._gecikme_rng = {y: random.Random(f"{self.ayar.tohum}-{y}-gecikme")
                             for y in (GCS2UAV, UAV2GCS)}
        self._kayip_rng = {y: random.Random(f"{self.ayar.tohum}-{y}-kayip")
                           for y in (GCS2UAV, UAV2GCS)}
        self._kuyruk: list = []
        self._sira = itertools.count()
        self._son_zaman = {GCS2UAV: 0.0, UAV2GCS: 0.0}
        self.sayac = {y: {"gelen": 0, "dusen": 0, "gonderilen": 0, "gecikme_toplam_s": 0.0}
                      for y in (GCS2UAV, UAV2GCS)}

    @property
    def temiz(self) -> bool:
        return self.ayar.temiz

    def _gecikme_sec_s(self, yon: str) -> float:
        a = self.ayar
        if a.gecikme_ms == 0 and a.jitter_ms == 0:
            return 0.0
        ms = self._gecikme_rng[yon].uniform(a.gecikme_ms - a.jitter_ms,
                                            a.gecikme_ms + a.jitter_ms)
        return max(ms, 0.0) / 1000.0

    def _duser_mi(self, yon: str) -> bool:
        return self._kayip_rng[yon].random() * 100.0 < self.ayar.kayip_yuzde

    def gonder(self, yon: str, is_: Callable[[], None]) -> bool:
        """Tek paketi zamanlar. Paket kaybolduysa False döndürür."""
        return self.toplu_gonder(yon, [is_]) == 1

    def toplu_gonder(self, yon: str, isler: list[Callable[[], None]]) -> int:
        """Aynı anda gelen paketleri zamanlar, kalan paket sayısını döndürür.

        Telsiz bir paket kümesini birlikte taşıdığı için gecikme küme başına,
        kayıp paket başına seçilir. Temiz kanalda işler hemen çalışır.
        """
        sayac = self.sayac[yon]
        sayac["gelen"] += len(isler)
        if self.temiz:
            for is_ in isler:
                is_()
                sayac["gonderilen"] += 1
            return len(isler)

        simdi = self.saat()
        zaman = max(simdi + self._gecikme_sec_s(yon), self._son_zaman[yon])
        kalan = 0
        for is_ in isler:
            if self._duser_mi(yon):
                sayac["dusen"] += 1
                continue
            heapq.heappush(self._kuyruk, (zaman, next(self._sira), simdi, yon, is_))
            kalan += 1
        self._son_zaman[yon] = zaman
        return kalan

    def sonraki_sure_s(self) -> float | None:
        """Sıradaki pakete kalan süre; kuyruk boşsa None."""
        if not self._kuyruk:
            return None
        return max(self._kuyruk[0][0] - self.saat(), 0.0)

    def zamani_gelenleri_gonder(self) -> None:
        """Zamanı gelen paketleri gönderir; proxy döngüsü her turda çağırır."""
        simdi = self.saat()
        while self._kuyruk and self._kuyruk[0][0] <= simdi:
            self._calistir(simdi)

    def bosalt(self) -> None:
        """Kapanışta kuyruktaki tüm paketleri gönderir."""
        while self._kuyruk:
            self._calistir(self.saat())

    def _calistir(self, simdi: float) -> None:
        _, _, gelis, yon, is_ = heapq.heappop(self._kuyruk)
        is_()
        self.sayac[yon]["gonderilen"] += 1
        self.sayac[yon]["gecikme_toplam_s"] += simdi - gelis

    def ozet(self) -> dict:
        """meta.json'daki kanal alanı: ayar ve ölçülen değerler."""
        olculen = {}
        for yon, s in self.sayac.items():
            olculen[yon] = {
                "gelen": s["gelen"],
                "dusen": s["dusen"],
                "gonderilen": s["gonderilen"],
                "olculen_kayip_yuzde": round(100.0 * s["dusen"] / s["gelen"], 3) if s["gelen"] else 0.0,
                "olculen_gecikme_ms": round(1000.0 * s["gecikme_toplam_s"] / s["gonderilen"], 3)
                if s["gonderilen"] else 0.0,
            }
        a = self.ayar
        return {"profil": a.profil, "gecikme_ms": a.gecikme_ms, "jitter_ms": a.jitter_ms,
                "kayip_yuzde": a.kayip_yuzde, "tohum": a.tohum, "olculen": olculen}


def ayar_olustur(cfg: dict, profil: str = "temiz", tohum: int = 0,
                 gecikme_ms: float | None = None, jitter_ms: float | None = None,
                 kayip_yuzde: float | None = None) -> KanalAyari:
    """config.yaml profilinden ayar üretir; verilen değerler profili ezer.

    Bilinmeyen profil için ValueError yükseltir.
    """
    profiller = cfg.get("kanal_profilleri") or {"temiz": {}}
    if profil not in profiller:
        raise ValueError(f"Bilinmeyen kanal profili '{profil}'. Geçerli: {sorted(profiller)}")
    p = profiller[profil] or {}
    ayar = KanalAyari(
        profil=profil,
        gecikme_ms=float(p.get("gecikme_ms", 0) if gecikme_ms is None else gecikme_ms),
        jitter_ms=float(p.get("jitter_ms", 0) if jitter_ms is None else jitter_ms),
        kayip_yuzde=float(p.get("kayip_yuzde", 0) if kayip_yuzde is None else kayip_yuzde),
        tohum=tohum,
    )
    if not 0 <= ayar.kayip_yuzde <= 100:
        raise ValueError(f"Kayıp yüzdesi 0-100 arasında olmalı: {ayar.kayip_yuzde}")
    return ayar
