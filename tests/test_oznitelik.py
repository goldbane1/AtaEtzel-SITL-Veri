# -*- coding: utf-8 -*-
"""oznitelik.py ve dogrula.py pencere kontrolleri için SITL'siz testler."""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "betikler"))

import dogrula  # noqa: E402
import komut_yanit  # noqa: E402
import ortak  # noqa: E402
import oznitelik  # noqa: E402
from oznitelik import KOMUT_ARALIGI_UST_S, pencere_tablosu  # noqa: E402

T0 = 2_000_000_000_000
G, U = "gcs2uav", "uav2gcs"


def paket(s, yon=U, ad="ATTITUDE", seq=0, sysid=1, compid=1, alanlar=None, label="normal"):
    return {
        "t_ns": T0 + int(s * 1e9), "direction": yon, "sysid": sysid, "compid": compid,
        "seq": seq, "msgname": ad, "fields_json": json.dumps(alanlar or {}), "label": label,
    }


def komut(s, no=400, seq=0, compid=0):
    return paket(s, G, "COMMAND_LONG", seq=seq, sysid=255, compid=compid, alanlar={"command": no})


def tablo(paketler, saldirilar=None):
    return pencere_tablosu(pd.DataFrame(paketler), "F100_normal", saldirilar)


def test_bosluklu_veride_pencereler_kesintisiz():
    sonuc = tablo([paket(0.2), paket(0.9), paket(5.3)])  # pencereler ilk paketten başlar
    assert len(sonuc) == 6
    assert (sonuc["window_start_ns"].diff().dropna() == 1_000_000_000).all()
    assert sonuc["window_start_ns"].iloc[0] == T0 + 200_000_000


def test_bos_pencerede_sayimlar_sifir():
    sonuc = tablo([paket(0.0), paket(3.5)])
    bos = sonuc.loc[1]
    assert bos["bos_pencere"] == 1
    assert bos["toplam_paket"] == 0 and bos["paket_uav2gcs"] == 0
    assert bos["n_ATTITUDE"] == 0 and bos["seq_atlama"] == 0
    assert bos["label"] == "normal" and bos["attack_ratio"] == 0
    assert sonuc.loc[0, "bos_pencere"] == 0


def test_son_paketten_beri_gecen_sure():
    sonuc = tablo([paket(0.0), paket(0.4), paket(3.5)])
    assert sonuc.loc[0, "son_paketten_beri_s"] == pytest.approx(0.6)
    assert sonuc.loc[2, "son_paketten_beri_s"] == pytest.approx(2.6)
    assert sonuc.loc[3, "son_paketten_beri_s"] == pytest.approx(0.5)


def test_bos_pencereye_dusen_zaman_asimi_kaybolmaz():
    # Komut 0,5'te gider, süre 3,5'te dolar; 3. pencerede hiç paket yok.
    sonuc = tablo([komut(0.5), paket(5.0)])
    assert sonuc.loc[3, "bos_pencere"] == 1
    assert sonuc.loc[3, "yanitsiz_komut"] == 1


def test_saldiri_araligi_sutunlari():
    saldiri = [{"attack_type": "flood", "start_ns": T0 + 1_500_000_000,
                "end_ns": T0 + 3_200_000_000}]
    sonuc = tablo([paket(s) for s in (0.0, 5.5)], saldiri)
    assert sonuc["saldiri_araliginda"].tolist() == [0, 1, 1, 1, 0, 0]
    assert sonuc["saldiri_turu_aralik"].tolist() == [
        "normal", "flood", "flood", "flood", "normal", "normal"]
    assert (sonuc["label"] == "normal").all()  # paket yok, label değişmez


def test_iki_saldiri_ortusurse_buyuk_ortusme_kazanir():
    saldirilar = [
        {"attack_type": "flood", "start_ns": T0, "end_ns": T0 + 200_000_000},
        {"attack_type": "replay", "start_ns": T0 + 200_000_000, "end_ns": T0 + 900_000_000},
    ]
    assert tablo([paket(0.0), paket(0.5)], saldirilar).loc[0, "saldiri_turu_aralik"] == "replay"


def test_etiket_sutunlari_en_sonda_ve_yasak_sutun_yok():
    sonuc = tablo([paket(0.0)])
    assert list(sonuc.columns)[-4:] == [
        "saldiri_araliginda", "saldiri_turu_aralik", "attack_ratio", "label"]
    assert not {"src_ip", "src_port", "raw_hex"} & set(sonuc.columns)


def test_yon_bazli_sayimlar_toplamla_tutarli():
    sonuc = tablo([paket(0.1, U, "HEARTBEAT", seq=0), paket(0.2, U, "HEARTBEAT", seq=1),
                   paket(0.3, G, "HEARTBEAT", seq=0, sysid=255, compid=0)])
    satir = sonuc.loc[0]
    assert satir["paket_gcs2uav"] + satir["paket_uav2gcs"] == satir["toplam_paket"] == 3
    assert (satir["n_g2u_HEARTBEAT"], satir["n_u2g_HEARTBEAT"]) == (1, 2)
    assert satir["n_HEARTBEAT"] == 3


def test_yon_bazli_zamanlama():
    sonuc = tablo([paket(0.0, U), paket(0.2, U), paket(0.1, G, sysid=255), paket(0.7, G, sysid=255)])
    assert sonuc.loc[0, "paket_arasi_ort_s_u2g"] == pytest.approx(0.2)
    assert sonuc.loc[0, "paket_arasi_ort_s_g2u"] == pytest.approx(0.6)


def test_iki_compid_karisinca_sahte_seq_atlamasi_yok():
    paketler = []
    for i in range(10):
        paketler.append(paket(i * 0.05, seq=i, compid=1))
        paketler.append(paket(i * 0.05 + 0.01, seq=100 + i, compid=2))
    sonuc = tablo(paketler)
    assert sonuc["seq_atlama"].sum() == 0
    assert sonuc["seq_tekrar"].sum() == 0


def test_pencere_sinirindaki_seq_atlamasi_sayilir():
    sonuc = tablo([paket(0.0, seq=4), paket(0.9, seq=5), paket(1.1, seq=9)])
    assert sonuc.loc[0, "seq_atlama"] == 0
    assert sonuc.loc[1, "seq_atlama"] == 1


def test_seq_255_ten_0_a_donus_atlama_degil():
    assert tablo([paket(0.1, seq=255), paket(0.2, seq=0)])["seq_atlama"].sum() == 0


def test_gcs_akislari_ve_sysid_seq_bozulmasi():
    # Saldırgan compid'i farklı akış olarak görünür, sysid içinde seq bozulur.
    sonuc = tablo([
        komut(0.1, seq=10, compid=0), komut(0.2, seq=0, compid=190),
        komut(0.3, seq=11, compid=0), komut(0.4, seq=1, compid=190),
    ])
    assert sonuc.loc[0, "gcs_akis_sayisi"] == 2
    assert sonuc.loc[0, "gcs_sysid_seq_bozulma"] == 3
    assert sonuc.loc[0, "seq_atlama"] == 0  # kaynak başına akışlar kusursuz


def test_compid_taklidinde_de_sysid_bozulmasi_yakalanir():
    sonuc = tablo([komut(0.1, seq=10), komut(0.2, seq=0), komut(0.3, seq=11)])
    assert sonuc.loc[0, "gcs_akis_sayisi"] == 1
    assert sonuc.loc[0, "gcs_sysid_seq_bozulma"] == 2


def test_uav2gcs_seq_sysid_bozulmasina_girmez():
    sonuc = tablo([paket(0.1, seq=1), paket(0.2, seq=50)])
    assert sonuc["gcs_sysid_seq_bozulma"].sum() == 0


def test_ayni_komut_tekrari_ve_kritik_komut():
    sonuc = tablo([komut(0.1, 176), komut(0.2, 176), komut(0.3, 176), komut(0.4, 520)])
    assert sonuc.loc[0, "ayni_komut_tekrari"] == 2
    assert sonuc.loc[0, "kritik_komut_sayisi"] == 3


def test_set_mode_kritik_sayilir():
    sonuc = tablo([paket(0.1, G, "SET_MODE", sysid=255, compid=0, alanlar={"custom_mode": 11})])
    assert sonuc.loc[0, "kritik_komut_sayisi"] == 1


def test_komut_araligi_onceki_pencereye_bakar():
    sonuc = tablo([paket(0.0), komut(0.9), komut(1.2), paket(2.5)])
    assert sonuc.loc[0, "komut_araligi_min_s"] == KOMUT_ARALIGI_UST_S
    assert sonuc.loc[1, "komut_araligi_min_s"] == pytest.approx(0.3)
    assert sonuc.loc[2, "komut_araligi_min_s"] == KOMUT_ARALIGI_UST_S


def _senaryo():
    p = [paket(i * 0.31, seq=i % 7) for i in range(30)]
    p += [komut(0.5, 176, seq=1), komut(0.8, 176, seq=9, compid=190), komut(2.9, 400, seq=2)]
    p.append(paket(3.0, U, "COMMAND_ACK", alanlar={"command": 400, "result": 4}))
    p += [komut(4.4, 300, seq=3), paket(8.8)]
    return p


@pytest.mark.parametrize("k", range(0, 9))
def test_nedensellik_gelecek_paketler_gecmisi_degistirmez(k):
    paketler = _senaryo()
    tam = tablo(paketler).drop(columns=["flight_id"])
    kesik = tablo([p for p in paketler if p["t_ns"] < T0 + (k + 1) * 1_000_000_000])
    kesik = kesik.drop(columns=["flight_id"])
    pd.testing.assert_frame_equal(
        tam.iloc[: len(kesik)].reset_index(drop=True), kesik, check_dtype=False
    )


# --- dogrula.py ----------------------------------------------------------
def test_kesintisiz_pencere_sorunsuz():
    paketler = pd.DataFrame([paket(0.0), paket(4.5)])
    assert dogrula.pencere_sorunlari(pencere_tablosu(paketler, "F100_normal"), paketler) == []


def test_kesintili_pencere_yakalanir():
    paketler = pd.DataFrame([paket(0.0), paket(4.5)])
    pencereler = pencere_tablosu(paketler, "F100_normal").drop(index=2)
    sorunlar = dogrula.pencere_sorunlari(pencereler, paketler)
    assert any("kesintili" in s for s in sorunlar)
    assert any("pencere sayısı" in s for s in sorunlar)


def test_dogrula_kesintili_ucusa_eksik_der(tmp_path, monkeypatch):
    monkeypatch.setattr(ortak, "repo_koku", lambda: tmp_path)
    cfg = {"veri_klasoru": "veri/ucuslar"}
    klasor = ortak.ucus_klasoru("F100_normal", cfg)
    klasor.mkdir(parents=True)
    paketler = pd.DataFrame([paket(0.0, U, "HEARTBEAT"), paket(4.5, G, "HEARTBEAT", sysid=255)])
    paketler.to_parquet(klasor / "paketler.parquet", index=False)
    (klasor / "meta.json").write_text(json.dumps({"flight_id": "F100_normal"}), encoding="utf-8")

    (tmp_path / "veri" / "oznitelikler").mkdir(parents=True)
    pencereler = pencere_tablosu(paketler, "F100_normal")
    yol = tmp_path / "veri" / "oznitelikler" / "pencereler.parquet"

    pencereler.to_parquet(yol, index=False)
    assert dogrula.bir_ucus_dogrula("F100_normal", cfg)

    pencereler.drop(index=2).to_parquet(yol, index=False)
    assert not dogrula.bir_ucus_dogrula("F100_normal", cfg)


def test_ana_akis_sutunlari_tam():
    sonuc = tablo([paket(0.0)])
    assert set(komut_yanit.SUTUNLAR) <= set(sonuc.columns)
