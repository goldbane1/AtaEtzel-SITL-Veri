#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""toplu_uretim.py — Gece boyu, insansız toplu uçuş üretimi.

Ana tohumdan bir uçuş planı çıkarır ve uçuşları sırayla yapar. Aynı ana tohum aynı
planı verir. Bir uçuş başarısız olursa loglanır, meta.json'a yazılır ve sıradakine
geçilir; tüm döngü durmaz.

UÇUŞLAR ARASINDA NE YAPILIYOR?
    Her uçuştan önce SITL YENİDEN BAŞLATILIR, yerinde resetlenmez. G0'da görüldü:
    Uçak bir önceki uçuştan havada kalıyor. Reset rüzgâr, EKF ve görev durumunu
    uçuştan uçuşa taşıyabilir; yeniden başlatmak ise bunu yapamaz ve saldırı bir
    uçağı bozsa bile sonraki uçuş temiz başlar. arduplane doğrudan ve her seferinde
    boş bir klasörde çalışır: EEPROM temizdir, xterm gerekmez, başsız makinede de çalışır.

--speedup 1 dışında bir hız KULLANILMAZ: Veri gerçek zamanlı olmalıdır.

Kullanım:
    python betikler/toplu_uretim.py --normal 4 --saldirili 2 \\
        --kanal-profilleri temiz,hafif,orta --ana-tohum 1
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import signal
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path

import ortak

SALDIRILAR = ("spoof_cmd", "impersonation", "replay", "flood", "fake_telemetry")
GOREVLER = ("gorev1_dikdortgen", "gorev2_uzunhat", "gorev3_loiter",
            "gorev4_karisik", "gorev5_farkli")

UCUS_SURESI_S = (180, 300)
RUZGAR_HIZ_MS = (0.0, 8.0)
TELEMETRI_HZ = (2, 4, 8)
IRTIFA_FARKI_M = (-30.0, 50.0)
SALDIRI_SURESI_S = (10.0, 45.0)
TEMIZ_BOLUM_S = 16.0              # RS-TCN son 16 pencereye bakar
SALDIRI_GECIKMESI_S = (TEMIZ_BOLUM_S, 60.0)
KALKIS_PAYI_S = 45.0              # uçuş başından kalkış doğrulanana kadar pay
EN_KISA_SALDIRI_S = 5.0

SPOOF_KOMUTLARI = (("mod_rtl", 0.45), ("mod_manual", 0.35), ("disarm", 0.20))
SPOOF_VARYANTLARI = ("tekrarli", "taklit_compid", "tek_atis")

SITL_HAZIR_SURESI_S = 60.0
UCUS_EK_SURE_S = 180.0            # kalkış beklemesi, kapanış vb. için pay


def _dengeli_dizi(ogeler, adet: int, rng: random.Random) -> list:
    """Öğeleri eşit sayıda dağıtıp karıştırır (fark en fazla 1)."""
    # Artan kısmı karıştırarak seç ki hep aynı öğeler fazladan gelmesin.
    tam = list(ogeler) * (adet // len(ogeler))
    artan = list(ogeler)
    rng.shuffle(artan)
    dizi = tam + artan[: adet - len(tam)]
    rng.shuffle(dizi)
    return dizi


def _saldiri_zamani(rng: random.Random, sure_s: float) -> tuple[float, float]:
    """Saldırı gecikmesi ve süresini seçer.

    Kalkıştan sonra en az 16 sn temiz bölüm ve saldırıdan sonra en az 16 sn temiz
    kuyruk kalır; uçuş kısaysa saldırı süresi kısaltılır.
    """
    gecikme = rng.uniform(*SALDIRI_GECIKMESI_S)
    en_cok = sure_s - KALKIS_PAYI_S - gecikme - TEMIZ_BOLUM_S
    if en_cok < EN_KISA_SALDIRI_S:
        gecikme = TEMIZ_BOLUM_S
        en_cok = sure_s - KALKIS_PAYI_S - gecikme - TEMIZ_BOLUM_S
    return round(gecikme, 1), round(min(rng.uniform(*SALDIRI_SURESI_S), en_cok), 1)


def _saldiri_argumanlari(saldiri: str, rng: random.Random) -> list[str]:
    """Saldırının alt türünü seçer (replay kaynağı uçuş anında seçilir)."""
    if saldiri == "spoof_cmd":
        komutlar, agirliklar = zip(*SPOOF_KOMUTLARI)
        argumanlar = ["--komut", rng.choices(komutlar, agirliklar)[0]]
        varyant = rng.choice(SPOOF_VARYANTLARI)
        if varyant == "taklit_compid":
            argumanlar.append("--taklit-compid")
        elif varyant == "tek_atis":
            argumanlar += ["--taklit-compid", "--tek-atis"]
        return argumanlar
    if saldiri == "flood":
        return ["--hiz", str(rng.randint(100, 500)), "--mesaj", rng.choice(("heartbeat", "ping"))]
    if saldiri == "impersonation":
        return ["--hiz", str(rng.randint(2, 10))]
    if saldiri == "fake_telemetry":
        return ["--sapma-m", str(rng.randint(50, 2000)), "--hiz", str(rng.randint(2, 8))]
    return ["--hiz", str(rng.randint(5, 20))]  # replay


def uretim_plani(normal: int, saldirili: int, profiller: list[str], ana_tohum: int) -> list[dict]:
    """Uçuş planını üretir. Replay'in kaynağı olabilsin diye normal uçuşlar önce gelir."""
    rng = random.Random(ana_tohum)
    toplam = normal + saldirili
    profil_dizisi = _dengeli_dizi(profiller, toplam, rng)
    saldiri_dizisi = _dengeli_dizi(SALDIRILAR, saldirili, rng) if saldirili else []

    plan: list[dict] = []
    for i in range(toplam):
        # Her uçuşun kendi tohumu vardır: Bir uçuşun seçimi diğerini kaydırmaz.
        ucus_tohumu = rng.randrange(2**31)
        u = random.Random(ucus_tohumu)
        sure = u.randint(*UCUS_SURESI_S)
        ucus = {
            "tur": "normal",
            "gorev": u.choice(GOREVLER),
            "sure_s": sure,
            "ruzgar_hiz": round(u.uniform(*RUZGAR_HIZ_MS), 1),
            "ruzgar_yon": u.randint(0, 359),
            "telemetri_hz": u.choice(TELEMETRI_HZ),
            "irtifa_farki_m": round(u.uniform(*IRTIFA_FARKI_M), 1),
            "kanal_profil": profil_dizisi[i],
            "ana_tohum": ana_tohum,
            "ucus_tohumu": ucus_tohumu,
            "kanal_tohumu": u.randrange(2**31),
        }
        if i >= normal:
            saldiri = saldiri_dizisi[i - normal]
            gecikme, saldiri_sure = _saldiri_zamani(u, sure)
            ucus.update(tur=saldiri, saldiri_gecikme_s=gecikme, saldiri_sure_s=saldiri_sure,
                        saldiri_argumanlari=_saldiri_argumanlari(saldiri, u))
        plan.append(ucus)
    return plan


def bos_numara_sayisi(cfg: dict) -> int:
    """Bu cihazın aralığında kalan boş uçuş numarası sayısı."""
    alt, ust = ortak.config_aralik_dogrula(cfg)
    kullanilan = [n for n in ortak._mevcut_numaralar(cfg) if alt <= n <= ust]
    return ust - (max(kullanilan) if kullanilan else alt - 1)


def replay_kaynagi_sec(cfg: dict, tohum: int) -> str | None:
    """Bu makinedeki başarılı normal uçuşlardan birini seçer; yoksa None."""
    kok = ortak.repo_koku() / cfg.get("veri_klasoru", "veri/ucuslar")
    adaylar = []
    if kok.exists():
        for ad in sorted(os.listdir(kok)):
            if ad.endswith("_normal") and (kok / ad / "paketler.parquet").exists() \
                    and not ortak.ucus_basarisiz_mi(ad, cfg) \
                    and (kok / ad / "meta.json").exists():
                adaylar.append(ad)
    return random.Random(tohum).choice(adaylar) if adaylar else None


class Sitl:
    """arduplane'i boş bir klasörde başlatır ve kapatır."""

    def __init__(self, cfg: dict) -> None:
        self.port = int(cfg.get("tcp_port", 5760))
        self.ardupilot = Path.home() / "ardupilot"
        self.surec: subprocess.Popen | None = None
        self.klasor: str | None = None

    def _port_acik(self) -> bool:
        return not ortak.port_bos_mu("127.0.0.1", self.port)

    def ac(self) -> bool:
        self.klasor = tempfile.mkdtemp(prefix="ataetzel_sitl_")
        komut = [
            str(self.ardupilot / "build/sitl/bin/arduplane"), "--model", "plane",
            "--speedup", "1", "--slave", "0",
            "--defaults", str(self.ardupilot / "Tools/autotest/models/plane.parm"),
            "--sim-address=127.0.0.1", "-I0",
        ]
        self.surec = subprocess.Popen(
            komut, cwd=self.klasor, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        bitis = time.time() + SITL_HAZIR_SURESI_S
        while time.time() < bitis:
            # Bağlanmadan bakılır: SITL ilk bağlantıyı proxy'den bekler.
            if ":%d " % self.port in subprocess.run(
                ["ss", "-tln"], capture_output=True, text=True
            ).stdout:
                return True
            if self.surec.poll() is not None:
                return False
            time.sleep(0.2)
        return False

    def kapat(self) -> None:
        if self.surec is not None and self.surec.poll() is None:
            os.killpg(self.surec.pid, signal.SIGTERM)
            try:
                self.surec.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(self.surec.pid, signal.SIGKILL)
                self.surec.wait()
        self.surec = None
        if self.klasor:
            shutil.rmtree(self.klasor, ignore_errors=True)
            self.klasor = None


def _ortam(ucus: dict) -> dict:
    ortam = dict(os.environ)
    ortam["KANAL_PROFIL"] = ucus["kanal_profil"]
    ortam["KANAL_TOHUM"] = str(ucus["kanal_tohumu"])
    ortam["UCUS_EK_ARG"] = (
        f"--tohum {ucus['ucus_tohumu']} --telemetri-hz {ucus['telemetri_hz']} "
        f"--irtifa-farki-m {ucus['irtifa_farki_m']}"
    )
    return ortam


def ucus_komutu(ucus: dict, ucus_id: str) -> list[str]:
    gorev = f"gorevler/{ucus['gorev']}.waypoints"
    if ucus["tur"] == "normal":
        return ["bash", "betikler/normal_uretim.sh", ucus_id, gorev, str(ucus["sure_s"]),
                str(ucus["ruzgar_hiz"]), str(ucus["ruzgar_yon"])]
    return ["bash", "betikler/saldiri_uret.sh", ucus_id, gorev, ucus["tur"],
            str(ucus["sure_s"]), str(ucus["saldiri_sure_s"]), str(ucus["saldiri_gecikme_s"]),
            *ucus["saldiri_argumanlari"]]


def _meta_isle(ucus_id: str, cfg: dict, ucus: dict, kod: int | None, neden: str | None) -> None:
    """Plan bilgisini ve (gerekirse) başarısızlığı meta.json'a yazar."""
    yol = ortak.ucus_klasoru_hazirla(ucus_id, cfg) / "meta.json"
    meta = {}
    if yol.exists():
        try:
            meta = json.loads(yol.read_text(encoding="utf-8"))
        except ValueError:
            meta = {}
    meta["flight_id"] = ucus_id
    meta["toplu_plan"] = ucus
    if ucus["tur"] == "normal":
        meta["wind"] = {"speed": ucus["ruzgar_hiz"], "dir": ucus["ruzgar_yon"]}
    if kod != 0:
        meta["ucus_basarili"] = False
        meta.setdefault("basarisizlik_nedeni", None)
        meta["basarisizlik_nedeni"] = meta["basarisizlik_nedeni"] or neden
    yol.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def bir_ucus_yap(ucus: dict, cfg: dict) -> tuple[str, bool]:
    """Tek uçuşu yapar. (uçuş adı, başarılı mı) döndürür; hata yükseltmez."""
    ucus = dict(ucus)
    ucus_id = ortak.sonraki_ucus_id(ucus["tur"], cfg)
    ortak.log(f"=== {ucus_id}: {ucus['gorev']}, {ucus['sure_s']} sn, "
              f"kanal {ucus['kanal_profil']} ===", "BILGI")

    if ucus["tur"] == "replay":
        kaynak = replay_kaynagi_sec(cfg, ucus["ucus_tohumu"])
        if kaynak is None:
            _meta_isle(ucus_id, cfg, ucus, 1, "replay için başarılı normal uçuş yok")
            ortak.log(f"{ucus_id}: replay kaynağı yok, atlandı.", "UYARI")
            return ucus_id, False
        ucus["saldiri_argumanlari"] = [*ucus["saldiri_argumanlari"], "--kaynak-ucus", kaynak]

    sitl = Sitl(cfg)
    kod: int | None = None
    neden = None
    try:
        if not sitl.ac():
            neden = "SITL başlatılamadı"
        else:
            try:
                kod = subprocess.run(
                    ucus_komutu(ucus, ucus_id), cwd=ortak.repo_koku(), env=_ortam(ucus),
                    timeout=ucus["sure_s"] + UCUS_EK_SURE_S,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                ).returncode
                if kod != 0:
                    neden = f"uçuş betiği {kod} koduyla bitti"
            except subprocess.TimeoutExpired:
                neden = "uçuş süresi aşıldı"
    finally:
        sitl.kapat()

    _meta_isle(ucus_id, cfg, ucus, kod, neden)
    basarili = kod == 0
    ortak.log(f"{ucus_id}: {'TAMAM' if basarili else 'BAŞARISIZ -> ' + str(neden)}",
              "TAMAM" if basarili else "UYARI")
    return ucus_id, basarili


def ozet_yaz(sonuclar: list[tuple[dict, str, bool]], sure_s: float) -> None:
    uretilen = sum(1 for _, _, b in sonuclar if b)
    print("")
    print("=" * 60)
    print(f"  Üretilen  : {uretilen}")
    print(f"  Başarısız : {len(sonuclar) - uretilen}")
    print(f"  Toplam süre: {sure_s / 60:.1f} dk")
    print("  Tür dağılımı:")
    for tur, adet in sorted(Counter(u["tur"] for u, _, b in sonuclar if b).items()):
        print(f"    {tur:<16} {adet}")
    print("  Kanal dağılımı:")
    for profil, adet in sorted(Counter(u["kanal_profil"] for u, _, b in sonuclar if b).items()):
        print(f"    {profil:<16} {adet}")
    for _, ucus_id, b in sonuclar:
        if not b:
            print(f"  BAŞARISIZ: {ucus_id}")
    print("=" * 60)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--normal", type=int, required=True, help="Normal uçuş sayısı.")
    ap.add_argument("--saldirili", type=int, required=True, help="Saldırılı uçuş sayısı.")
    ap.add_argument("--kanal-profilleri", default="temiz", help="Virgülle ayrılmış profil listesi.")
    ap.add_argument("--ana-tohum", type=int, required=True, help="Planın ana tohumu.")
    ap.add_argument("--isleme", action=argparse.BooleanOptionalAction, default=True,
                    help="Sonunda etiketle, oznitelik ve dogrula çalıştır.")
    args = ap.parse_args()

    cfg = ortak.config_oku()
    profiller = [p.strip() for p in args.kanal_profilleri.split(",") if p.strip()]
    gecerli = cfg.get("kanal_profilleri") or {}
    if not profiller or any(p not in gecerli for p in profiller):
        ortak.hata_ve_cik(f"Kanal profilleri geçersiz: {profiller}. Geçerli: {sorted(gecerli)}")

    plan = uretim_plani(args.normal, args.saldirili, profiller, args.ana_tohum)
    bos = bos_numara_sayisi(cfg)
    if len(plan) > bos:
        ortak.hata_ve_cik(
            f"{len(plan)} uçuş için numara yetmiyor: Bu cihazda {bos} boş numara var. "
            "Ayrıntı: belgeler/UCUS_NUMARALARI.md"
        )
    if not ortak.port_bos_mu("127.0.0.1", int(cfg.get("tcp_port", 5760))):
        ortak.hata_ve_cik("TCP 5760 dolu: Açık kalmış bir SITL var, önce onu kapatın.")

    baslangic = time.time()
    sonuclar = []
    for sira, ucus in enumerate(plan, 1):
        ortak.log(f"Uçuş {sira}/{len(plan)}", "BILGI")
        ucus_id, basarili = bir_ucus_yap(ucus, cfg)
        sonuclar.append((ucus, ucus_id, basarili))

    if args.isleme:
        betikler = Path(__file__).resolve().parent
        for betik in ("etiketle.py", "oznitelik.py", "dogrula.py"):
            subprocess.run(["python", str(betikler / betik), "--hepsi"], check=False)

    ozet_yaz(sonuclar, time.time() - baslangic)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
