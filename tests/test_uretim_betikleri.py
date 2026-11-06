# -*- coding: utf-8 -*-
"""Üretim betiklerinin başarısız uçuş davranışı için SITL'siz testler.

Gerçek Python betikleri yerine sahte bir `python` komutu kullanılır; böylece
yalnızca kabuk betiklerinin akışı (çıkış kodu, saldırının başlatılması) sınanır.
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent

SAHTE_PYTHON = """#!/usr/bin/env bash
# Hangi betik çağrıldıysa ona göre davran.
case "$1" in
  betikler/ortak.py) exit 0 ;;
  betikler/kayit_proxy.py) exit 0 ;;
  betikler/ucus_yap.py)
    if [[ "${SAHTE_UCUS_KODU}" == "0" ]]; then
      while [[ $# -gt 0 ]]; do
        if [[ "$1" == "--kalkis-isareti" ]]; then touch "$2"; fi
        shift
      done
    fi
    exit "${SAHTE_UCUS_KODU}" ;;
  betikler/saldirilar/*) touch "${SALDIRI_IZI}"; exit 0 ;;
esac
exit 0
"""

SALDIRI_ARG = ["F101_spoof_cmd", "gorev.waypoints", "spoof_cmd", "180", "30", "60"]


def _ortam_kur(tmp_path):
    """Betikleri .venv olmayan geçici bir kopyaya alır, sahte python'u kurar."""
    repo = tmp_path / "repo"
    (repo / "betikler" / "saldirilar").mkdir(parents=True)
    for ad in ("normal_uretim.sh", "saldiri_uret.sh"):
        shutil.copy(KOK / "betikler" / ad, repo / "betikler" / ad)
    (repo / "betikler" / "saldirilar" / "spoof_cmd.py").write_text("", encoding="utf-8")

    bin_klasoru = tmp_path / "bin"
    bin_klasoru.mkdir()
    python = bin_klasoru / "python"
    python.write_text(SAHTE_PYTHON, encoding="utf-8")
    python.chmod(python.stat().st_mode | stat.S_IXUSR)
    return repo, bin_klasoru


def _calistir(repo, bin_klasoru, betik, argumanlar, ucus_kodu, iz):
    ortam = dict(os.environ)
    ortam["PATH"] = f"{bin_klasoru}{os.pathsep}{ortam['PATH']}"
    ortam["SAHTE_UCUS_KODU"] = str(ucus_kodu)
    ortam["SALDIRI_IZI"] = str(iz)
    return subprocess.run(
        ["bash", str(repo / "betikler" / betik), *argumanlar],
        env=ortam, capture_output=True, text=True, timeout=30,
    )


def test_kalkis_olmazsa_saldiri_baslamaz_ve_hata_doner(tmp_path):
    repo, bin_klasoru = _ortam_kur(tmp_path)
    iz = tmp_path / "saldiri_calisti"
    sonuc = _calistir(repo, bin_klasoru, "saldiri_uret.sh", SALDIRI_ARG, 1, iz)
    assert sonuc.returncode == 1
    assert not iz.exists()
    assert "saldırı başlatılmadı" in sonuc.stdout
    assert "[TAMAM] Saldırılı" not in sonuc.stdout


def test_kalkis_olursa_saldiri_baslar_ve_basarili_doner(tmp_path):
    repo, bin_klasoru = _ortam_kur(tmp_path)
    iz = tmp_path / "saldiri_calisti"
    sonuc = _calistir(repo, bin_klasoru, "saldiri_uret.sh", SALDIRI_ARG, 0, iz)
    assert sonuc.returncode == 0
    assert iz.exists()
    assert "[TAMAM] Saldırılı" in sonuc.stdout


def test_normal_uretim_basarisiz_ucusta_hata_doner(tmp_path):
    repo, bin_klasoru = _ortam_kur(tmp_path)
    sonuc = _calistir(
        repo, bin_klasoru, "normal_uretim.sh",
        ["F100_normal", "gorev.waypoints"], 1, tmp_path / "iz",
    )
    assert sonuc.returncode == 1
    assert "[TAMAM] Normal" not in sonuc.stdout
    assert "Uçuş başarısız" in sonuc.stdout
