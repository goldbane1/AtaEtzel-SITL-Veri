# -*- coding: utf-8 -*-
"""komut_yanit.py için SITL gerektirmeyen testler.

Paketler elle kurulur: (saniye, yön, mesaj adı, alanlar).
"""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "betikler"))

import komut_yanit  # noqa: E402
import ortak  # noqa: E402
import oznitelik  # noqa: E402
from komut_yanit import SUTUNLAR, komut_yanit_oznitelikleri  # noqa: E402

T0 = 1_000_000_000_000
ARM = 400
DO_SET_MODE = 176
AUTO, LOITER, RTL = 10, 12, 11
G, U = "gcs2uav", "uav2gcs"


def tablo(paketler, sysid=1):
    return pd.DataFrame([
        {
            "t_ns": T0 + int(s * 1e9), "direction": yon, "sysid": sysid,
            "msgname": ad, "fields_json": json.dumps(alanlar),
        }
        for s, yon, ad, alanlar in paketler
    ])


def hesapla(paketler, son_s=None):
    """Paketleri işler. son_s verilirse kayıt o ana kadar uzatılır."""
    paketler = list(paketler)
    if son_s is not None:
        paketler.append((son_s, U, "ATTITUDE", {}))
    return komut_yanit_oznitelikleri(tablo(paketler), T0)


def komut(s, no=ARM):
    return (s, G, "COMMAND_LONG", {"command": no})


def ack(s, no=ARM, sonuc=0):
    return (s, U, "COMMAND_ACK", {"command": no, "result": sonuc})


def hb(s, mod, tip=1, otopilot=3):
    return (s, U, "HEARTBEAT", {"type": tip, "autopilot": otopilot, "custom_mode": mod})


def mod_komutu(s, mod):
    return (s, G, "COMMAND_LONG", {"command": DO_SET_MODE, "param2": float(mod)})


def toplam(sonuc, sutun):
    return int(sonuc[sutun].sum())


def test_sutunlar_ve_siralari():
    sonuc = hesapla([komut(0.1), ack(0.2)])
    assert list(sonuc.columns) == SUTUNLAR
    assert len(SUTUNLAR) == 10


# --- Komut ↔ ACK ---------------------------------------------------------
def test_eslesen_ack_gecikmesi():
    sonuc = hesapla([komut(0.1), ack(0.15), komut(1.1), ack(1.3)])
    assert sonuc.loc[0, "ack_eslesme_sayisi"] == 1
    assert sonuc.loc[0, "ack_gecikme_ort_ms"] == pytest.approx(50, abs=0.01)
    assert sonuc.loc[1, "ack_gecikme_max_ms"] == pytest.approx(200, abs=0.01)
    assert toplam(sonuc, "yanitsiz_komut") == 0


def test_ayni_pencerede_ort_ve_max():
    sonuc = hesapla([komut(0.0), komut(0.1), ack(0.2), ack(0.5)])
    assert sonuc.loc[0, "ack_eslesme_sayisi"] == 2
    assert sonuc.loc[0, "ack_gecikme_ort_ms"] == pytest.approx(300, abs=0.01)
    assert sonuc.loc[0, "ack_gecikme_max_ms"] == pytest.approx(400, abs=0.01)


def test_farkli_komutun_acki_eslesmez():
    sonuc = hesapla([komut(0.1, ARM), ack(0.2, 300)], son_s=5)
    assert toplam(sonuc, "eslesmeyen_ack") == 1
    assert toplam(sonuc, "ack_eslesme_sayisi") == 0
    assert toplam(sonuc, "yanitsiz_komut") == 1


def test_yanitsiz_komut_zaman_asiminin_doldugu_pencerede():
    sonuc = hesapla([komut(0.5)], son_s=6)
    assert sonuc.loc[0, "yanitsiz_komut"] == 0
    assert sonuc.loc[3, "yanitsiz_komut"] == 1
    assert toplam(sonuc, "yanitsiz_komut") == 1


def test_tam_uc_saniyede_gelen_ack_zamanindadir():
    sonuc = hesapla([komut(0.5), ack(3.5)], son_s=6)
    assert toplam(sonuc, "ack_eslesme_sayisi") == 1
    assert toplam(sonuc, "yanitsiz_komut") == 0


def test_gec_gelen_ack_eslesmez():
    sonuc = hesapla([komut(0.5), ack(4.0)], son_s=6)
    assert sonuc.loc[3, "yanitsiz_komut"] == 1
    assert sonuc.loc[4, "eslesmeyen_ack"] == 1
    assert toplam(sonuc, "ack_eslesme_sayisi") == 0


def test_komutsuz_ack_eslesmeyen():
    assert hesapla([ack(1.0)]).loc[1, "eslesmeyen_ack"] == 1


def test_reddedilen_ack():
    sonuc = hesapla([komut(0.1), ack(0.2, sonuc=4)])
    assert sonuc.loc[0, "ack_red"] == 1
    assert sonuc.loc[0, "ack_eslesme_sayisi"] == 1


def test_isleniyor_acki_nihai_yanit_degildir():
    sonuc = hesapla([komut(0.1), ack(0.2, sonuc=5), ack(0.4, sonuc=0)])
    assert toplam(sonuc, "ack_eslesme_sayisi") == 1
    assert toplam(sonuc, "ack_red") == 0
    assert sonuc.loc[0, "ack_gecikme_ort_ms"] == pytest.approx(300, abs=0.01)


def test_yon_onemlidir():
    # Uçaktan gelen COMMAND_LONG komut sayılmaz; gcs2uav yönündeki ACK de yanıt değildir.
    sonuc = hesapla([
        (0.1, U, "COMMAND_LONG", {"command": ARM}),
        (0.2, G, "COMMAND_ACK", {"command": ARM, "result": 0}),
    ], son_s=5)
    assert toplam(sonuc, "yanitsiz_komut") == 0
    assert toplam(sonuc, "ack_eslesme_sayisi") == 0
    assert toplam(sonuc, "eslesmeyen_ack") == 0


def test_sysid_kullanilmaz():
    paketler = [komut(0.1), ack(0.2), hb(0.3, AUTO), hb(0.4, RTL)]
    birinci = komut_yanit_oznitelikleri(tablo(paketler, sysid=1), T0)
    ikinci = komut_yanit_oznitelikleri(tablo(paketler, sysid=99), T0)
    pd.testing.assert_frame_equal(birinci, ikinci)


def test_command_int_de_komuttur():
    sonuc = hesapla([(0.1, G, "COMMAND_INT", {"command": 192}), ack(0.2, 192)])
    assert toplam(sonuc, "ack_eslesme_sayisi") == 1


# --- Görev akışı ---------------------------------------------------------
def gorev_akisi(s=0.0, adet=2):
    paketler = [(s, G, "MISSION_CLEAR_ALL", {}),
                (s + 0.01, U, "MISSION_ACK", {"type": 0}),
                (s + 0.02, G, "MISSION_COUNT", {"count": adet})]
    for i in range(adet):
        paketler.append((s + 0.03 + i * 0.02, U, "MISSION_REQUEST", {"seq": i}))
        paketler.append((s + 0.04 + i * 0.02, G, "MISSION_ITEM", {"seq": i}))
    paketler.append((s + 0.5, U, "MISSION_ACK", {"type": 0}))
    return paketler


def test_dogru_gorev_akisi_ihlal_degil():
    assert toplam(hesapla(gorev_akisi()), "gorev_protokol_ihlali") == 0


def test_mission_request_int_ve_item_int_kabul_edilir():
    sonuc = hesapla([
        (0.0, G, "MISSION_COUNT", {"count": 1}),
        (0.1, U, "MISSION_REQUEST_INT", {"seq": 0}),
        (0.2, G, "MISSION_ITEM_INT", {"seq": 0}),
        (0.3, U, "MISSION_ACK", {"type": 0}),
    ])
    assert toplam(sonuc, "gorev_protokol_ihlali") == 0


def test_istenmeyen_gorev_noktasi_ihlaldir():
    # Replay saldırısının tipik izi: kimse istemeden MISSION_ITEM.
    sonuc = hesapla([(1.2, G, "MISSION_ITEM", {"seq": 3})])
    assert sonuc.loc[1, "gorev_protokol_ihlali"] == 1


def test_yanlis_sira_numarasi_ihlaldir():
    sonuc = hesapla([
        (0.0, G, "MISSION_COUNT", {"count": 2}),
        (0.1, U, "MISSION_REQUEST", {"seq": 0}),
        (0.2, G, "MISSION_ITEM", {"seq": 1}),
    ])
    assert toplam(sonuc, "gorev_protokol_ihlali") == 1


def test_akissiz_istek_ve_ack_ihlaldir():
    sonuc = hesapla([(0.1, U, "MISSION_REQUEST", {"seq": 0}),
                     (0.2, U, "MISSION_ACK", {"type": 0})])
    assert toplam(sonuc, "gorev_protokol_ihlali") == 2


def test_eksik_nokta_ile_ack_ihlaldir():
    sonuc = hesapla([
        (0.0, G, "MISSION_COUNT", {"count": 2}),
        (0.1, U, "MISSION_REQUEST", {"seq": 0}),
        (0.2, G, "MISSION_ITEM", {"seq": 0}),
        (0.3, U, "MISSION_ACK", {"type": 0}),
    ])
    assert toplam(sonuc, "gorev_protokol_ihlali") == 1


def test_basarisiz_gorev_acki_ihlaldir():
    sonuc = hesapla([(0.0, G, "MISSION_COUNT", {"count": 0}),
                     (0.1, U, "MISSION_ACK", {"type": 1})])
    assert toplam(sonuc, "gorev_protokol_ihlali") == 1


def test_akis_surerken_yeni_mission_count_ihlaldir():
    sonuc = hesapla([(0.0, G, "MISSION_COUNT", {"count": 2}),
                     (0.1, G, "MISSION_COUNT", {"count": 2})])
    assert toplam(sonuc, "gorev_protokol_ihlali") == 1


# --- PARAM ---------------------------------------------------------------
def test_param_yanitlandi():
    sonuc = hesapla([(0.1, G, "PARAM_SET", {"param_id": "SIM_WIND_SPD"}),
                     (0.2, U, "PARAM_VALUE", {"param_id": "SIM_WIND_SPD"})], son_s=5)
    assert toplam(sonuc, "param_yanitsiz") == 0


def test_param_yanitsiz_zaman_asiminda_sayilir():
    sonuc = hesapla([(0.5, G, "PARAM_SET", {"param_id": "YOK"})], son_s=5)
    assert sonuc.loc[3, "param_yanitsiz"] == 1


def test_baska_parametrenin_degeri_yanit_degildir():
    sonuc = hesapla([(0.5, G, "PARAM_SET", {"param_id": "A"}),
                     (0.6, U, "PARAM_VALUE", {"param_id": "B"})], son_s=5)
    assert toplam(sonuc, "param_yanitsiz") == 1


# --- Mod -----------------------------------------------------------------
def test_istenen_mod_degisimi_tutarlidir():
    sonuc = hesapla([hb(0.0, AUTO), mod_komutu(1.0, RTL), ack(1.1, DO_SET_MODE),
                     hb(2.0, RTL)], son_s=6)
    assert toplam(sonuc, "mod_tutarsiz") == 0
    assert toplam(sonuc, "komutsuz_mod_degisimi") == 0


def test_set_mode_mesaji_ack_beklemez():
    sonuc = hesapla([hb(0.0, AUTO), (1.0, G, "SET_MODE", {"custom_mode": RTL}),
                     hb(2.0, RTL)], son_s=6)
    assert toplam(sonuc, "yanitsiz_komut") == 0
    assert toplam(sonuc, "mod_tutarsiz") == 0
    assert toplam(sonuc, "komutsuz_mod_degisimi") == 0


def test_kabul_edilip_uygulanmayan_mod_tutarsizdir():
    sonuc = hesapla([hb(0.0, AUTO), mod_komutu(1.5, RTL), ack(1.6, DO_SET_MODE),
                     hb(2.0, AUTO), hb(3.0, AUTO)], son_s=6)
    assert sonuc.loc[4, "mod_tutarsiz"] == 1


def test_reddedilen_mod_komutu_tutarsiz_sayilmaz():
    sonuc = hesapla([hb(0.0, AUTO), mod_komutu(1.0, RTL),
                     ack(1.1, DO_SET_MODE, sonuc=4)], son_s=6)
    assert toplam(sonuc, "mod_tutarsiz") == 0
    assert toplam(sonuc, "ack_red") == 1


def test_zaten_o_moddaysa_beklenmez():
    sonuc = hesapla([hb(0.0, RTL), mod_komutu(1.0, RTL),
                     ack(1.1, DO_SET_MODE)], son_s=6)
    assert toplam(sonuc, "mod_tutarsiz") == 0


def test_komutsuz_mod_degisimi():
    sonuc = hesapla([hb(0.0, AUTO), hb(2.0, LOITER)])
    assert sonuc.loc[2, "komutsuz_mod_degisimi"] == 1


def test_baska_moda_gecis_komutsuz_sayilir():
    sonuc = hesapla([hb(0.0, AUTO), mod_komutu(1.0, RTL), hb(2.0, LOITER)], son_s=6)
    assert sonuc.loc[2, "komutsuz_mod_degisimi"] == 1
    assert toplam(sonuc, "mod_tutarsiz") == 1


def test_acilis_modundan_cikis_sayilmaz():
    sonuc = hesapla([hb(0.0, komut_yanit.MOD_INITIALISING), hb(1.0, 0)])
    assert toplam(sonuc, "komutsuz_mod_degisimi") == 0


def test_yer_istasyonu_heartbeati_modu_degistirmez():
    sonuc = hesapla([hb(0.0, AUTO), hb(1.0, 0, tip=6, otopilot=8), hb(2.0, AUTO)])
    assert toplam(sonuc, "komutsuz_mod_degisimi") == 0


# --- Nedensellik ---------------------------------------------------------
def karisik_senaryo():
    return [
        hb(0.0, AUTO), komut(0.3), ack(0.4), komut(1.2),  # yanıtsız kalacak
        mod_komutu(1.6, RTL), ack(1.7, DO_SET_MODE),
        (2.1, G, "PARAM_SET", {"param_id": "A"}), hb(2.2, AUTO), hb(3.2, AUTO),
        (3.4, G, "MISSION_ITEM", {"seq": 1}), komut(3.6, 300), hb(4.2, LOITER),
        ack(4.3, 300), (5.3, U, "PARAM_VALUE", {"param_id": "A"}), ack(5.5),
        hb(5.6, LOITER), hb(6.6, LOITER), (7.5, U, "ATTITUDE", {}), (8.5, U, "ATTITUDE", {}),
    ]


@pytest.mark.parametrize("k", range(0, 9))
def test_gelecek_paketler_gecmis_pencereleri_degistirmez(k):
    """k. pencereden sonraki paketler silinince 0..k pencereleri aynı kalmalı."""
    paketler = karisik_senaryo()
    tam = hesapla(paketler)
    sinir = (k + 1)
    kesik = hesapla([p for p in paketler if p[0] < sinir])
    pd.testing.assert_frame_equal(
        tam.iloc[: len(kesik)].reset_index(drop=True), kesik, check_dtype=False
    )


def test_senaryoda_olaylar_beklenen_pencerelerde():
    sonuc = hesapla(karisik_senaryo())
    assert sonuc.loc[4, "yanitsiz_komut"] == 1     # 1,2 + 3 = 4,2
    assert sonuc.loc[4, "mod_tutarsiz"] == 1       # 1,6 + 3 = 4,6
    assert sonuc.loc[5, "param_yanitsiz"] == 1     # 2,1 + 3 = 5,1
    assert sonuc.loc[5, "eslesmeyen_ack"] == 1     # 5,5'teki geç ACK


def test_sirasiz_verilen_paketler_zamana_gore_islenir():
    paketler = [ack(0.2), komut(0.1)]
    assert toplam(hesapla(paketler), "ack_eslesme_sayisi") == 1


def test_bozuk_json_atlanir():
    df = tablo([komut(0.1), ack(0.2)])
    df.loc[0, "fields_json"] = "{bozuk"
    sonuc = komut_yanit_oznitelikleri(df, T0)
    assert toplam(sonuc, "eslesmeyen_ack") == 1


# --- oznitelik.py ile birleşme -------------------------------------------
def test_oznitelik_ciktisinda_sutunlar_var(tmp_path):
    df = tablo([komut(0.1), ack(0.2), (2.5, U, "ATTITUDE", {})])
    for sutun, deger in [("seq", 0), ("compid", 1), ("length", 9)]:
        df[sutun] = deger
    df["label"] = "normal"
    cfg = {"veri_klasoru": str(tmp_path)}
    klasor = ortak.ucus_klasoru("F100_normal", cfg)
    klasor.mkdir(parents=True)
    df.to_parquet(klasor / "paketler.parquet", index=False)

    sonuc = oznitelik.bir_ucus_oznitelik("F100_normal", cfg)

    assert set(SUTUNLAR) <= set(sonuc.columns)
    assert list(sonuc.columns)[-2:] == ["attack_ratio", "label"]
    assert sonuc.loc[0, "ack_eslesme_sayisi"] == 1
    assert sonuc.loc[0, "ack_gecikme_ort_ms"] == pytest.approx(100, abs=0.01)
    assert not {"src_ip", "src_port", "raw_hex"} & set(sonuc.columns)
