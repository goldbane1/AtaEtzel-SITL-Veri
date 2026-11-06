#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kayit_yazici.py — Paketleri ana döngüyü durdurmadan diske yazar.

Eski yöntem her yazmada tüm dosyayı okuyup baştan yazıyordu. Dosya büyüdükçe bu
süre artıyor ve proxy o sırada paket işleyemiyordu; zaman damgalarının doğruluğu
buna bağlıdır. AkisYazici ise:

  - Paketleri kuyruğa alır (ekle() hiç beklemez).
  - Ayrı bir iş parçacığında pyarrow ParquetWriter ile row group olarak yazar.
  - Şema açıktır; tipler paketten pakete değişmez.

BEKLENMEDİK SONLANMA
    ParquetWriter kapanmadan biterse (kill -9, elektrik kesintisi) dosyanın sonundaki
    özet yazılmaz ve dosya TAMAMEN okunamaz. Bu yüzden her parti aynı anda bir kurtarma
    günlüğüne de yazılır (Arrow IPC akışı; sonu eksik olsa da okunabilir). Düzgün
    kapanışta günlük silinir. Günlük kaldıysa kurtar() Parquet'i yeniden üretir;
    kaybedilen veri en fazla son YAZMA_ARALIGI_S kadardır.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

YAZMA_ARALIGI_S = 1.0      # en fazla bu kadar veri riske girer
PARTI_PAKET_ESIGI = 500    # kuyruk bu kadar dolunca erken yazılır
KURTARMA_EKI = ".kurtarma.arrows"

# paketler.parquet şeması. Sıra ve adlar VERI_SEMASI.md ile birebir aynıdır.
SEMA = pa.schema([
    ("t_ns", pa.int64()),
    ("direction", pa.string()),
    ("src_ip", pa.string()),
    ("src_port", pa.int64()),
    ("sysid", pa.int64()),
    ("compid", pa.int64()),
    ("seq", pa.int64()),
    ("msgid", pa.int64()),
    ("msgname", pa.string()),
    ("length", pa.int64()),
    ("is_signed", pa.bool_()),
    ("crc_ok", pa.bool_()),
    ("fields_json", pa.string()),
    ("raw_hex", pa.string()),
])
SUTUNLAR = SEMA.names


def kurtarma_yolu(parquet_yolu: Path) -> Path:
    """Bir parquet dosyasının kurtarma günlüğünün yolu."""
    return Path(str(parquet_yolu) + KURTARMA_EKI)


class AkisYazici:
    """Paketleri arka planda Parquet'e yazan yazıcı."""

    def __init__(self, parquet_yolu: Path) -> None:
        self.parquet_yolu = Path(parquet_yolu)
        self.kuyruk: deque[dict] = deque()
        self.hata: Exception | None = None
        self.yazilan_paket = 0
        self._dur = threading.Event()
        self._is: threading.Thread | None = None
        self._parquet: pq.ParquetWriter | None = None
        self._gunluk_dosya = None
        self._gunluk = None

    def baslat(self) -> None:
        self._is = threading.Thread(target=self._calis, name="kayit-yazici", daemon=True)
        self._is.start()

    def ekle(self, satir: dict) -> None:
        """Paketi kuyruğa alır. Ana döngüden çağrılır, beklemez."""
        self.kuyruk.append(satir)

    def _calis(self) -> None:
        son_yazma = time.monotonic()
        while not self._dur.wait(YAZMA_ARALIGI_S / 4):
            aralik_doldu = time.monotonic() - son_yazma >= YAZMA_ARALIGI_S
            if aralik_doldu or len(self.kuyruk) >= PARTI_PAKET_ESIGI:
                self._guvenli_bosalt()
                son_yazma = time.monotonic()
        self._guvenli_bosalt()

    def _guvenli_bosalt(self) -> None:
        try:
            self.bosalt()
        except Exception as e:  # iş parçacığı sessizce ölmesin; kapat() bildirir
            self.hata = e

    def bosalt(self) -> None:
        """Kuyruktaki paketleri bir row group olarak yazar."""
        satirlar = []
        while self.kuyruk:
            satirlar.append(self.kuyruk.popleft())
        if not satirlar:
            return
        parti = pa.RecordBatch.from_pylist(satirlar, schema=SEMA)

        if self._parquet is None:
            self._gunluk_dosya = pa.OSFile(str(kurtarma_yolu(self.parquet_yolu)), "wb")
            self._gunluk = pa.ipc.new_stream(self._gunluk_dosya, SEMA)
            self._parquet = pq.ParquetWriter(str(self.parquet_yolu), SEMA)
        # Önce günlük: kesinti olursa veri orada durur.
        self._gunluk.write_batch(parti)
        self._gunluk_dosya.flush()
        self._parquet.write_batch(parti)
        self.yazilan_paket += len(satirlar)

    def kapat(self) -> None:
        """Kalan paketleri yazar, dosyayı düzgün kapatır, günlüğü siler."""
        self._dur.set()
        if self._is is not None:
            self._is.join()
        else:
            self._guvenli_bosalt()
        if self._parquet is not None:
            self._parquet.close()
            self._gunluk.close()
            self._gunluk_dosya.close()
            kurtarma_yolu(self.parquet_yolu).unlink(missing_ok=True)
        if self.hata is not None:
            raise self.hata


def kurtar(parquet_yolu: Path) -> int:
    """Beklenmedik sonlanmadan sonra Parquet'i günlükten yeniden üretir.

    Kurtarılan paket sayısını döndürür. Günlüğün yarım kalan son partisi atlanır.
    """
    parquet_yolu = Path(parquet_yolu)
    gunluk = kurtarma_yolu(parquet_yolu)
    gecici = Path(str(parquet_yolu) + ".gecici")
    toplam = 0
    with pa.OSFile(str(gunluk), "rb") as kaynak, pq.ParquetWriter(str(gecici), SEMA) as hedef:
        okuyucu = pa.ipc.open_stream(kaynak)
        while True:
            try:
                parti = okuyucu.read_next_batch()
            except (StopIteration, pa.ArrowInvalid, OSError):
                break
            hedef.write_batch(parti)
            toplam += parti.num_rows
    gecici.replace(parquet_yolu)
    gunluk.unlink()
    return toplam
