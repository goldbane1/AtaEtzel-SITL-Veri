# -*- coding: utf-8 -*-
"""kayit_yazici.py ve proxy kapanışı için SITL gerektirmeyen testler."""

import signal
import socket
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "betikler"))

from pymavlink.dialects.v20 import ardupilotmega as mavlink2  # noqa: E402

import proxy_performans  # noqa: E402
from kayit_yazici import SUTUNLAR, AkisYazici, kurtar, kurtarma_yolu  # noqa: E402


def satir(i):
    return {
        "t_ns": 1_000 + i, "direction": "uav2gcs", "src_ip": "127.0.0.1", "src_port": 5760,
        "sysid": 1, "compid": 1, "seq": i % 256, "msgid": 30, "msgname": "ATTITUDE",
        "length": 39, "is_signed": False, "crc_ok": True, "fields_json": "{}", "raw_hex": "fd",
    }


def test_sutunlar_semayla_ayni():
    assert SUTUNLAR == ["t_ns", "direction", "src_ip", "src_port", "sysid", "compid", "seq",
                        "msgid", "msgname", "length", "is_signed", "crc_ok", "fields_json",
                        "raw_hex"]


def test_akis_yazici_tum_paketleri_sirayla_yazar(tmp_path):
    yol = tmp_path / "p.parquet"
    y = AkisYazici(yol)
    y.baslat()
    for i in range(1200):
        y.ekle(satir(i))
    y.kapat()
    df = pd.read_parquet(yol)
    assert df["t_ns"].tolist() == [1_000 + i for i in range(1200)]
    assert not kurtarma_yolu(yol).exists()


def test_birden_fazla_row_group_yazilir(tmp_path):
    yol = tmp_path / "p.parquet"
    y = AkisYazici(yol)
    for bas in (0, 10, 20):
        for i in range(bas, bas + 10):
            y.ekle(satir(i))
        y.bosalt()
    y.kapat()
    assert pq.ParquetFile(yol).num_row_groups == 3


def test_paket_yoksa_dosya_olusmaz(tmp_path):
    yol = tmp_path / "p.parquet"
    y = AkisYazici(yol)
    y.baslat()
    y.kapat()
    assert not yol.exists()


def test_eski_ve_yeni_yontem_ayni_okunur(tmp_path):
    satirlar = [satir(i) for i in range(50)]
    eski_yol, yeni_yol = tmp_path / "eski.parquet", tmp_path / "yeni.parquet"
    pd.DataFrame(satirlar, columns=SUTUNLAR).to_parquet(eski_yol, index=False)
    y = AkisYazici(yeni_yol)
    for s in satirlar:
        y.ekle(s)
    y.kapat()
    eski, yeni = pd.read_parquet(eski_yol), pd.read_parquet(yeni_yol)
    assert list(eski.columns) == list(yeni.columns)
    pd.testing.assert_frame_equal(eski, yeni)


def test_gercek_eski_ucus_varsa_ayni_sema(tmp_path):
    yol = KOK / "veri" / "ucuslar" / "F102_normal" / "paketler.parquet"
    if not yol.exists():
        pytest.skip("eski uçuş yok")
    eski = pd.read_parquet(yol)[SUTUNLAR].head(20)
    yeni_yol = tmp_path / "yeni.parquet"
    y = AkisYazici(yeni_yol)
    for s in eski.to_dict("records"):
        y.ekle(s)
    y.kapat()
    pd.testing.assert_frame_equal(eski, pd.read_parquet(yeni_yol))


def test_kurtarma_gunlugu_yarim_son_partiyi_atlar(tmp_path):
    yol = tmp_path / "p.parquet"
    y = AkisYazici(yol)
    for bas in (0, 100):
        for i in range(bas, bas + 100):
            y.ekle(satir(i))
        y.bosalt()
    # Kesinti benzetimi: kapatmadan dosyaları bırak, günlüğün sonunu kes.
    gunluk = kurtarma_yolu(yol)
    y._gunluk_dosya.flush()
    kopya = gunluk.read_bytes()
    gunluk.write_bytes(kopya[:-40])
    yol.write_bytes(b"yarim")
    assert kurtar(yol) == 100
    assert pd.read_parquet(yol)["t_ns"].tolist() == [1_000 + i for i in range(100)]
    assert not gunluk.exists()


CALISTIRICI = textwrap.dedent("""
    import sys
    sys.path.insert(0, {betikler!r})
    import kayit_proxy
    cfg = {{"veri_klasoru": {klasor!r}, "host": "127.0.0.1", "udp_port": 0,
            "hava_enjeksiyon_port": 0, "tcp_port": {port}}}
    kayit_proxy.proxy_calistir("F100_normal", cfg)
""")


class SahteSitl:
    """Proxy'nin bağlandığı, istenince paket gönderen TCP sunucusu."""

    def __init__(self):
        self.sunucu = socket.socket()
        self.sunucu.bind(("127.0.0.1", 0))
        self.sunucu.listen(1)
        self.port = self.sunucu.getsockname()[1]
        self.gonderilen = 0
        self.baglanti = None

    def gonder(self, adet):
        if self.baglanti is None:
            self.baglanti, _ = self.sunucu.accept()
        uretici = mavlink2.MAVLink(None, 1, 1)
        for _ in range(adet):
            self.baglanti.sendall(uretici.heartbeat_encode(1, 3, 0, 0, 0).pack(uretici))
            self.gonderilen += 1

    def kapat(self):
        if self.baglanti:
            self.baglanti.close()
        self.sunucu.close()


def _proxy_baslat(tmp_path, sitl):
    kod = CALISTIRICI.format(betikler=str(KOK / "betikler"), klasor=str(tmp_path), port=sitl.port)
    return subprocess.Popen([sys.executable, "-c", kod], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)


@pytest.mark.parametrize("sinyal", [signal.SIGINT, signal.SIGTERM])
def test_duzgun_kapanista_dosya_saglam_ve_kayipsiz(tmp_path, sinyal):
    sitl = SahteSitl()
    surec = _proxy_baslat(tmp_path, sitl)
    sitl.gonder(300)
    time.sleep(0.5)
    surec.send_signal(sinyal)
    surec.wait(timeout=10)
    yol = tmp_path / "F100_normal" / "paketler.parquet"
    assert len(pd.read_parquet(yol)) == 300
    assert not kurtarma_yolu(yol).exists()
    sitl.kapat()


def test_kill_9_sonrasi_veri_kurtarilir(tmp_path):
    sitl = SahteSitl()
    surec = _proxy_baslat(tmp_path, sitl)
    sitl.gonder(300)
    time.sleep(2.5)                    # ilk parti diske insin
    surec.kill()
    surec.wait(timeout=10)
    yol = tmp_path / "F100_normal" / "paketler.parquet"
    assert yol.exists() and kurtarma_yolu(yol).exists()
    with pytest.raises(Exception):
        pd.read_parquet(yol)           # düzgün kapanmayan parquet okunamaz
    assert kurtar(yol) == 300
    assert len(pd.read_parquet(yol)) == 300
    sitl.kapat()


def test_performans_olcumu_kisa(tmp_path):
    s = proxy_performans.olc(2.0, 200, tmp_path)
    assert s["kaydedilen"] == s["gonderilen"]
    assert s["ortalama_ms"] > 0
