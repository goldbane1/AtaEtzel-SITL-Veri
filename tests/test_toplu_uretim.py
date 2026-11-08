# -*- coding: utf-8 -*-
"""toplu_uretim.py ve başarısız uçuş ayıklaması için SITL'siz testler."""

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "betikler"))

import dogrula  # noqa: E402
import etiketle  # noqa: E402
import ortak  # noqa: E402
import toplu_uretim  # noqa: E402
from toplu_uretim import (EN_KISA_SALDIRI_S, KALKIS_PAYI_S, SALDIRILAR, TEMIZ_BOLUM_S,  # noqa: E402
                          ucus_komutu, uretim_plani)

PROFILLER = ["temiz", "hafif", "orta"]


def test_ayni_tohum_ayni_plan_farkli_tohum_farkli():
    assert uretim_plani(4, 2, PROFILLER, 1) == uretim_plani(4, 2, PROFILLER, 1)
    assert uretim_plani(4, 2, PROFILLER, 1) != uretim_plani(4, 2, PROFILLER, 2)


def test_uyeler_ve_siralama():
    plan = uretim_plani(4, 2, PROFILLER, 1)
    assert [u["tur"] == "normal" for u in plan] == [True] * 4 + [False] * 2
    assert len(plan) == 6


@pytest.mark.parametrize("tohum", range(50))
def test_parametreler_araliklarda(tohum):
    for u in uretim_plani(6, 10, PROFILLER, tohum):
        assert f"{u['gorev']}.waypoints" in {p.name for p in (KOK / "gorevler").iterdir()}
        assert 180 <= u["sure_s"] <= 300
        assert 0 <= u["ruzgar_hiz"] <= 8
        assert 0 <= u["ruzgar_yon"] <= 359
        assert u["telemetri_hz"] in (2, 4, 8)
        assert -30 <= u["irtifa_farki_m"] <= 50
        assert u["kanal_profil"] in PROFILLER


@pytest.mark.parametrize("tohum", range(50))
def test_saldiri_temiz_bolum_kurali(tohum):
    for u in uretim_plani(0, 15, PROFILLER, tohum):
        assert u["saldiri_gecikme_s"] >= TEMIZ_BOLUM_S
        assert u["saldiri_sure_s"] >= EN_KISA_SALDIRI_S
        bitis = KALKIS_PAYI_S + u["saldiri_gecikme_s"] + u["saldiri_sure_s"]
        assert bitis + TEMIZ_BOLUM_S <= u["sure_s"] + 0.01


@pytest.mark.parametrize("adet", [1, 2, 5, 7, 10, 23])
def test_saldiri_turleri_dengeli(adet):
    sayim = Counter(u["tur"] for u in uretim_plani(0, adet, PROFILLER, 3))
    assert sum(sayim.values()) == adet
    assert set(sayim) <= set(SALDIRILAR)
    degerler = [sayim.get(s, 0) for s in SALDIRILAR]
    assert max(degerler) - min(degerler) <= 1


def test_kanal_profilleri_her_turun_icinde_dengeli():
    plan = uretim_plani(10, 20, PROFILLER, 3)
    for tur in ("normal", *SALDIRILAR):
        sayim = Counter(u["kanal_profil"] for u in plan if u["tur"] == tur)
        adetler = [sayim[p] for p in PROFILLER]
        assert max(adetler) - min(adetler) <= 1, tur


def test_spoof_cogunlukla_etkili_ve_varyantlar_gorulur():
    argumanlar = []
    for tohum in range(40):
        for u in uretim_plani(0, 10, PROFILLER, tohum):
            if u["tur"] == "spoof_cmd":
                argumanlar.append(u["saldiri_argumanlari"])
    assert len(argumanlar) > 50
    disarm = sum("disarm" in a for a in argumanlar)
    assert disarm / len(argumanlar) < 0.35
    assert any("--taklit-compid" in a for a in argumanlar)
    assert any("--tek-atis" in a for a in argumanlar)


def test_speedup_kullanilmaz():
    kaynak = (KOK / "betikler" / "toplu_uretim.py").read_text(encoding="utf-8")
    assert '"--speedup", "1"' in kaynak
    assert kaynak.count("--speedup") == 2  # biri açıklama, biri 1 değeri


def test_saldiri_komutu_dogru_argumanlari_tasir():
    u = uretim_plani(0, 1, PROFILLER, 1)[0]
    komut = ucus_komutu(u, "F120_x")
    assert komut[:5] == ["bash", "betikler/saldiri_uret.sh", "F120_x",
                         f"gorevler/{u['gorev']}.waypoints", u["tur"]]
    assert komut[5:8] == [str(u["sure_s"]), str(u["saldiri_sure_s"]), str(u["saldiri_gecikme_s"])]


def _cfg(tmp_path, alt=100, ust=149):
    return {"pc_id": "pc1", "ucus_no_araligi": [alt, ust], "veri_klasoru": str(tmp_path)}


def test_bos_numara_sayisi(tmp_path):
    assert toplu_uretim.bos_numara_sayisi(_cfg(tmp_path)) == 50
    (tmp_path / "F111_normal").mkdir()
    assert toplu_uretim.bos_numara_sayisi(_cfg(tmp_path)) == 38


def _ucus(tmp_path, ad, basarili=True, paket=True):
    k = tmp_path / ad
    k.mkdir()
    (k / "meta.json").write_text(json.dumps({"flight_id": ad, "ucus_basarili": basarili}),
                                 encoding="utf-8")
    if paket:
        (k / "paketler.parquet").write_bytes(b"x")


def test_replay_kaynagi_yalnizca_basarili_normal(tmp_path):
    cfg = _cfg(tmp_path)
    _ucus(tmp_path, "F100_normal", basarili=False)
    _ucus(tmp_path, "F101_flood")
    assert toplu_uretim.replay_kaynagi_sec(cfg, 1) is None
    _ucus(tmp_path, "F102_normal")
    assert toplu_uretim.replay_kaynagi_sec(cfg, 1) == "F102_normal"


def test_ucus_basarisiz_mi(tmp_path):
    cfg = _cfg(tmp_path)
    _ucus(tmp_path, "F100_normal", basarili=False)
    _ucus(tmp_path, "F101_normal")
    assert ortak.ucus_basarisiz_mi("F100_normal", cfg)
    assert not ortak.ucus_basarisiz_mi("F101_normal", cfg)
    assert not ortak.ucus_basarisiz_mi("F102_normal", cfg)


def test_basarisiz_ucus_sonraki_ucusu_durdurmaz(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(ortak, "repo_koku", lambda: tmp_path)

    class SahteSitl:
        def __init__(self, cfg):
            pass

        def ac(self):
            return False

        def kapat(self):
            pass

    monkeypatch.setattr(toplu_uretim, "Sitl", SahteSitl)
    u = uretim_plani(2, 0, ["temiz"], 1)
    sonuclar = [toplu_uretim.bir_ucus_yap(x, cfg) for x in u]
    assert [b for _, b in sonuclar] == [False, False]
    assert [a for a, _ in sonuclar] == ["F100_normal", "F101_normal"]
    meta = json.loads((tmp_path / "F100_normal" / "meta.json").read_text(encoding="utf-8"))
    assert meta["ucus_basarili"] is False
    assert meta["basarisizlik_nedeni"] == "SITL başlatılamadı"
    assert meta["toplu_plan"]["ana_tohum"] == 1
    assert meta["toplu_plan"]["ucus_tohumu"] == u[0]["ucus_tohumu"]


def test_saldiri_zamanlama_kontrolu():
    s = [{"attack_type": "flood", "start_ns": 20 * 10**9, "end_ns": 30 * 10**9}]
    assert dogrula.saldiri_zamanlama_sorunlari(s, 2 * 10**9, 50 * 10**9) == []
    assert dogrula.saldiri_zamanlama_sorunlari(s, 10 * 10**9, 50 * 10**9)
    assert dogrula.saldiri_zamanlama_sorunlari(s, 2 * 10**9, 40 * 10**9)
    assert dogrula.saldiri_zamanlama_sorunlari(s, None, 50 * 10**9) == []


def test_gecikmeli_son_saldiri_paketi_etiketlenir(tmp_path):
    cfg = _cfg(tmp_path)
    klasor = ortak.ucus_klasoru("F100_flood", cfg)
    klasor.mkdir()
    pd.DataFrame([
        {"t_ns": 100, "src_ip": "127.0.0.1", "src_port": 9},
        {"t_ns": 300_000_100, "src_ip": "127.0.0.1", "src_port": 9},   # bitişten 0,3 sn sonra
        {"t_ns": 150, "src_ip": "127.0.0.1", "src_port": 5},           # başka adres
    ]).to_parquet(klasor / "paketler.parquet", index=False)
    ortak.ground_truth_ekle("F100_flood", {
        "attack_type": "flood", "start_ns": 50, "end_ns": 200,
        "attacker_addr": "127.0.0.1:9", "params": {},
    }, cfg)
    etiketle.bir_ucus_etiketle("F100_flood", cfg)
    assert pd.read_parquet(klasor / "paketler.parquet")["label"].tolist() == [
        "flood", "flood", "normal"]


def test_uyku_engeli_alinamazsa_uretim_durmaz(monkeypatch, capsys):
    monkeypatch.setattr(toplu_uretim.shutil, "which", lambda ad: None)
    assert toplu_uretim.uyku_engelle() is None
    assert "uykuya geçmediğinden" in capsys.readouterr().out
    toplu_uretim.uyku_serbest_birak(None)


@pytest.mark.parametrize("no", [1, 2, 3, 4, 5])
def test_bes_makinenin_bloklari_gecerli(no):
    alt, ust = no * 100, no * 100 + 99
    assert ortak.config_aralik_dogrula(
        {"pc_id": f"pc{no}", "ucus_no_araligi": [alt, ust]}) == (alt, ust)


def test_makine_baska_makinenin_blogunu_kullanamaz():
    with pytest.raises(SystemExit):
        ortak.config_aralik_dogrula({"pc_id": "pc4", "ucus_no_araligi": [500, 599]})
