#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""komut_yanit.py — Komut–yanıt tutarlılığı öznitelikleri.

BU DOSYA NE YAPAR?
    MAVLink'te yer istasyonu bir şey ister, uçak da yanıt verir. Saldırıların
    izi çoğu zaman paket sayısında değil, bu "istek ↔ yanıt" ilişkisinde görülür:

      - Kimsenin istemediği bir ACK geldi mi?
      - Uçak verilen komuta hiç yanıt vermedi mi?
      - Kimse istemediği hâlde uçuş modu değişti mi?

    Literatürdeki çalışmalar çoğunlukla yalnızca uçaktan gelen yöne bakar. Biz
    iki yönü birlikte kullanıyoruz; projenin özgün katkılarından biri budur
    (bkz. belgeler/MIMARI.md, s2).

GİRDİ VE ÇIKTI
    Girdi : Bir uçuşun paketleri (paketler.parquet). Kullanılan sütunlar:
            t_ns, direction, msgname, fields_json.
    Çıktı : Her 1 sn'lik pencere için SUTUNLAR listesindeki 10 sayı.

    Bu 10 sayı RS-TCN'e diğer özniteliklerle birlikte girer.

ÜÇ TEMEL KURAL (bu dosyayı değiştirirken bozmayın)
    1. NEDENSELLİK: Model gerçek zamanlı çalışacak, geleceği göremez. Bu yüzden
       paketleri zaman sırasıyla, tek tek işliyoruz. Bir pencerenin değeri
       yalnızca o pencerenin bitişine kadarki paketlere bağlıdır.
    2. ZAMAN AŞIMI OLAYI: "Yanıt gelmedi" bilgisi komutun gönderildiği anda
       bilinemez, ancak 3 sn dolunca bilinir. Bu yüzden yanıtsız komut,
       gönderildiği pencerede değil ZAMAN AŞIMININ DOLDUĞU pencerede sayılır.
    3. SYSID KULLANILMAZ: Eşleştirme yön + içerikle yapılır. Saldırgan sysid'i
       kolayca taklit eder; ona güvenmek hem yanıltıcı olur hem de modelin
       saldırganı kimliğinden ezberlemesine yol açar. src_ip, src_port ve
       raw_hex de burada KULLANILMAZ (veri sızıntısı).

KISALTMALAR
    gcs2uav : yer istasyonundan uçağa giden paket
    uav2gcs : uçaktan yer istasyonuna giden paket
    ACK     : COMMAND_ACK, uçağın "komutunu aldım, sonucu şu" yanıtı
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict, deque

import pandas as pd

PENCERE_NS = 1_000_000_000      # pencere uzunluğu: 1 sn
ZAMAN_ASIMI_NS = 3_000_000_000  # bir yanıt için beklenen en uzun süre: 3 sn

GCS2UAV = "gcs2uav"
UAV2GCS = "uav2gcs"

# COMMAND_ACK içindeki "result" değerleri (MAV_RESULT).
ACK_KABUL = 0          # ACCEPTED: komut kabul edildi
ACK_ISLENIYOR = 5      # IN_PROGRESS: komut sürüyor, asıl sonuç sonra gelecek

MAV_CMD_DO_SET_MODE = 176  # COMMAND_LONG ile mod değiştirme komutu

# HEARTBEAT alanlarındaki değerler.
MAV_TYPE_GCS = 6           # type: bu HEARTBEAT bir yer istasyonundan
MAV_AUTOPILOT_INVALID = 8  # autopilot: gönderen bir otopilot değil
MOD_INITIALISING = 16      # ArduPlane'in açılış modu; ondan çıkış normaldir

# Üretilen sütunlar. Sıra ve adlar VERI_SEMASI.md ile aynıdır.
SUTUNLAR = [
    "ack_gecikme_ort_ms",     # eşleşen ACK'lerin ortalama gecikmesi (ms)
    "ack_gecikme_max_ms",     # eşleşen ACK'lerin en büyük gecikmesi (ms)
    "ack_eslesme_sayisi",     # bir komutla eşleşen ACK sayısı
    "yanitsiz_komut",         # 3 sn içinde ACK gelmeyen komut sayısı
    "eslesmeyen_ack",         # hiçbir bekleyen komuta ait olmayan ACK sayısı
    "ack_red",                # sonucu "kabul" olmayan ACK sayısı
    "gorev_protokol_ihlali",  # görev yükleme akışına uymayan mesaj sayısı
    "param_yanitsiz",         # 3 sn içinde PARAM_VALUE gelmeyen PARAM_SET sayısı
    "mod_tutarsiz",           # istenen moda 3 sn içinde geçilmeyen istek sayısı
    "komutsuz_mod_degisimi",  # kimse istemeden gerçekleşen mod değişimi sayısı
]

# Yalnızca bu mesajlar bizi ilgilendirir; diğerlerinin JSON'u hiç çözülmez.
ILGILI_MESAJLAR = {
    "COMMAND_LONG", "COMMAND_INT", "COMMAND_ACK",
    "MISSION_CLEAR_ALL", "MISSION_COUNT", "MISSION_REQUEST",
    "MISSION_REQUEST_INT", "MISSION_ITEM", "MISSION_ITEM_INT", "MISSION_ACK",
    "PARAM_SET", "PARAM_VALUE",
    "SET_MODE", "HEARTBEAT",
}


class KomutYanitHesaplayici:
    """Paketleri zaman sırasıyla okuyup pencere sayaçlarını dolduran sınıf.

    Bu sınıf, gerçek zamanlı çalışan bir gözlemci gibi davranır: paket_isle()
    her çağrıldığında yalnızca o ana kadar gördüklerini bilir. İleride aynı
    mantık güvenlik duvarında canlı olarak da kullanılabilir.
    """

    def __init__(self, t0_ns: int, pencere_ns: int = PENCERE_NS) -> None:
        self.t0_ns = t0_ns
        self.pencere_ns = pencere_ns

        # Sonuçlar: pencere numarası -> sayaçlar.
        self.sayaclar: defaultdict[int, Counter] = defaultdict(Counter)
        self.gecikmeler_ms: defaultdict[int, list[float]] = defaultdict(list)

        # Bekleyen komutlar: komut numarası -> gönderilme zamanları (en eski başta).
        self.bekleyen_komutlar: defaultdict[int, deque[int]] = defaultdict(deque)

        # Bekleyen PARAM_SET'ler: parametre adı -> gönderilme zamanları.
        self.bekleyen_paramlar: defaultdict[str, deque[int]] = defaultdict(deque)

        # Uçuş modu takibi.
        self.guncel_mod: int | None = None
        # Mod istekleri: (istenen mod, istek zamanı), en eski başta.
        self.mod_istekleri: deque[tuple[int, int]] = deque()

        # Görev yükleme akışının durumu.
        self.gorev_gonderen: str | None = None  # akışı başlatan yön; None = akış yok
        self.gorev_beklenen_adet = 0
        self.gorev_alinanlar: set[int] = set()
        self.gorev_istenen_sira: int | None = None
        self.temizleme_ack_bekleyen = 0  # MISSION_CLEAR_ALL da MISSION_ACK alır

    # -----------------------------------------------------------------
    # Yardımcılar
    # -----------------------------------------------------------------
    def _pencere(self, t_ns: int) -> int:
        """Bir zaman damgasının düştüğü pencerenin numarası."""
        return (t_ns - self.t0_ns) // self.pencere_ns

    def _say(self, t_ns: int, sutun: str) -> None:
        """t_ns anının penceresindeki sayacı bir artırır."""
        self.sayaclar[self._pencere(t_ns)][sutun] += 1

    # -----------------------------------------------------------------
    # Zaman aşımları
    # -----------------------------------------------------------------
    def zaman_asimlarini_isle(self, simdi_ns: int) -> None:
        """Süresi `simdi_ns` anına kadar dolmuş beklemeleri kapatır.

        Dikkat: Olay, bu fonksiyonun çağrıldığı pencereye değil, sürenin
        DOLDUĞU ana yazılır. Araya hiç paket girmese bile doğru pencere bulunur.
        Tam 3. sn'de gelen yanıt hâlâ zamanındadır (bu yüzden `<` kullanılır).
        """
        for gonderim_zamanlari in self.bekleyen_komutlar.values():
            while gonderim_zamanlari and gonderim_zamanlari[0] + ZAMAN_ASIMI_NS < simdi_ns:
                bitis = gonderim_zamanlari.popleft() + ZAMAN_ASIMI_NS
                self._say(bitis, "yanitsiz_komut")

        for gonderim_zamanlari in self.bekleyen_paramlar.values():
            while gonderim_zamanlari and gonderim_zamanlari[0] + ZAMAN_ASIMI_NS < simdi_ns:
                bitis = gonderim_zamanlari.popleft() + ZAMAN_ASIMI_NS
                self._say(bitis, "param_yanitsiz")

        while self.mod_istekleri and self.mod_istekleri[0][1] + ZAMAN_ASIMI_NS < simdi_ns:
            _, istek_zamani = self.mod_istekleri.popleft()
            self._say(istek_zamani + ZAMAN_ASIMI_NS, "mod_tutarsiz")

    # -----------------------------------------------------------------
    # 1) Komut ↔ COMMAND_ACK
    # -----------------------------------------------------------------
    def _komut_gonderildi(self, t_ns: int, alanlar: dict) -> None:
        """Yer istasyonundan bir komut çıktı; ACK beklemeye başla."""
        komut = int(alanlar["command"])
        self.bekleyen_komutlar[komut].append(t_ns)

        # DO_SET_MODE bir mod isteğidir; param2 istenen modu taşır.
        if komut == MAV_CMD_DO_SET_MODE:
            self._mod_istendi(t_ns, int(alanlar.get("param2", -1)))

    def _ack_alindi(self, t_ns: int, alanlar: dict) -> None:
        """Uçaktan COMMAND_ACK geldi; bekleyen en eski aynı komutla eşleştir."""
        komut = int(alanlar["command"])
        sonuc = int(alanlar.get("result", ACK_KABUL))

        # "Komut sürüyor" nihai yanıt değildir; asıl ACK'i beklemeye devam et.
        if sonuc == ACK_ISLENIYOR:
            return

        bekleyenler = self.bekleyen_komutlar[komut]
        if bekleyenler:
            gonderim = bekleyenler.popleft()
            pencere = self._pencere(t_ns)
            self.sayaclar[pencere]["ack_eslesme_sayisi"] += 1
            self.gecikmeler_ms[pencere].append((t_ns - gonderim) / 1e6)
        else:
            # Bekleyen komut yok: ya kimse istemedi ya da ACK çok geç geldi.
            self._say(t_ns, "eslesmeyen_ack")

        if sonuc != ACK_KABUL:
            self._say(t_ns, "ack_red")
            # Reddedilen mod komutunda modun değişmemesi tutarlıdır;
            # o isteği beklemeyi bırak.
            if komut == MAV_CMD_DO_SET_MODE and self.mod_istekleri:
                self.mod_istekleri.popleft()

    # -----------------------------------------------------------------
    # 2) Görev yükleme akışı
    # -----------------------------------------------------------------
    # Doğru akış şöyledir (N noktalı görev için):
    #
    #   gönderen  --MISSION_COUNT(N)-->  alıcı
    #   gönderen  <--MISSION_REQUEST(0)-- alıcı
    #   gönderen  --MISSION_ITEM(0)-->   alıcı
    #        ... N nokta boyunca tekrar ...
    #   gönderen  <--MISSION_ACK--        alıcı
    #
    # Sırası bozuk her mesaj bir ihlaldir. Örneğin replay saldırısı eski
    # MISSION_ITEM'ları kimse istemeden gönderir.
    def _gorev_ihlali(self, t_ns: int) -> None:
        self._say(t_ns, "gorev_protokol_ihlali")

    def _gorev_akisini_bitir(self) -> None:
        self.gorev_gonderen = None
        self.gorev_beklenen_adet = 0
        self.gorev_alinanlar = set()
        self.gorev_istenen_sira = None

    def _gorev_mesaji(self, t_ns: int, yon: str, msgname: str, alanlar: dict) -> None:
        if msgname == "MISSION_CLEAR_ALL":
            if yon == GCS2UAV:
                self.temizleme_ack_bekleyen += 1

        elif msgname == "MISSION_COUNT":
            # Akış sürerken yeni bir akış başlatılamaz.
            if self.gorev_gonderen is not None:
                self._gorev_ihlali(t_ns)
            self._gorev_akisini_bitir()
            self.gorev_gonderen = yon
            self.gorev_beklenen_adet = int(alanlar.get("count", 0))

        elif msgname in ("MISSION_REQUEST", "MISSION_REQUEST_INT"):
            # İstek, akışı başlatanın karşı tarafından gelmeli.
            if self.gorev_gonderen is None or yon == self.gorev_gonderen:
                self._gorev_ihlali(t_ns)
            else:
                self.gorev_istenen_sira = int(alanlar.get("seq", -1))

        elif msgname in ("MISSION_ITEM", "MISSION_ITEM_INT"):
            sira = int(alanlar.get("seq", -1))
            # Nokta yalnızca akışı başlatandan ve istenen sıra numarasıyla gelebilir.
            if (self.gorev_gonderen is None or yon != self.gorev_gonderen
                    or sira != self.gorev_istenen_sira):
                self._gorev_ihlali(t_ns)
            else:
                self.gorev_alinanlar.add(sira)
                self.gorev_istenen_sira = None

        elif msgname == "MISSION_ACK":
            # Önce: bu ACK önceki MISSION_CLEAR_ALL'ın yanıtı olabilir.
            if yon == UAV2GCS and self.temizleme_ack_bekleyen > 0:
                self.temizleme_ack_bekleyen -= 1
                return
            if self.gorev_gonderen is None or yon == self.gorev_gonderen:
                self._gorev_ihlali(t_ns)
                return
            # Başarısız sonuç ya da eksik nokta da ihlaldir.
            eksik = len(self.gorev_alinanlar) < self.gorev_beklenen_adet
            if int(alanlar.get("type", 0)) != 0 or eksik:
                self._gorev_ihlali(t_ns)
            self._gorev_akisini_bitir()

    # -----------------------------------------------------------------
    # 3) PARAM_SET ↔ PARAM_VALUE
    # -----------------------------------------------------------------
    def _param_set(self, t_ns: int, alanlar: dict) -> None:
        self.bekleyen_paramlar[str(alanlar.get("param_id", ""))].append(t_ns)

    def _param_value(self, alanlar: dict) -> None:
        # Uçak, kendiliğinden de PARAM_VALUE yollayabilir (ör. istatistikler).
        # Bu yüzden eşleşmeyen PARAM_VALUE ihlal sayılmaz.
        bekleyenler = self.bekleyen_paramlar[str(alanlar.get("param_id", ""))]
        if bekleyenler:
            bekleyenler.popleft()

    # -----------------------------------------------------------------
    # 4) Uçuş modu
    # -----------------------------------------------------------------
    def _mod_istendi(self, t_ns: int, istenen_mod: int) -> None:
        # Uçak zaten o moddaysa beklenecek bir değişim yoktur.
        if istenen_mod != self.guncel_mod:
            self.mod_istekleri.append((istenen_mod, t_ns))

    def _heartbeat(self, t_ns: int, alanlar: dict) -> None:
        """Uçağın HEARTBEAT'i: mod değişti mi, değiştiyse biri istedi mi?"""
        # Yer istasyonu veya otopilot olmayan bileşenlerin HEARTBEAT'i modu söylemez.
        if (int(alanlar.get("type", 0)) == MAV_TYPE_GCS
                or int(alanlar.get("autopilot", 0)) == MAV_AUTOPILOT_INVALID):
            return

        yeni_mod = int(alanlar.get("custom_mode", 0))
        onceki_mod = self.guncel_mod
        self.guncel_mod = yeni_mod
        if onceki_mod is None or yeni_mod == onceki_mod:
            return

        # Bu moda geçiş isteği var mıydı? Varsa hepsi yerine getirilmiş olur.
        istek_vardi = any(mod == yeni_mod for mod, _ in self.mod_istekleri)
        self.mod_istekleri = deque(
            istek for istek in self.mod_istekleri if istek[0] != yeni_mod
        )

        # Açılış modundan çıkış otomatiktir, sayılmaz. Görev sonunda RTL'ye geçiş
        # gibi meşru otomatik değişimler ise SAYILIR: model bunların normal
        # uçuşta da görüldüğünü buradan öğrenir.
        if not istek_vardi and onceki_mod != MOD_INITIALISING:
            self._say(t_ns, "komutsuz_mod_degisimi")

    # -----------------------------------------------------------------
    # Ana giriş noktası
    # -----------------------------------------------------------------
    def paket_isle(self, t_ns: int, yon: str, msgname: str, alanlar: dict) -> None:
        """Tek bir paketi işler. Paketler zaman sırasıyla verilmelidir."""
        # Önce bu pakete kadar süresi dolanları kapat: bir yanıt 3 sn'den geç
        # geldiyse eşleşmemeli.
        self.zaman_asimlarini_isle(t_ns)

        if yon == GCS2UAV:
            if msgname in ("COMMAND_LONG", "COMMAND_INT"):
                self._komut_gonderildi(t_ns, alanlar)
            elif msgname == "SET_MODE":
                # Plane-4.7.2 SET_MODE'a COMMAND_ACK göndermez, bu yüzden
                # ACK beklenmez; yalnızca mod değişimi izlenir.
                self._mod_istendi(t_ns, int(alanlar.get("custom_mode", -1)))
            elif msgname == "PARAM_SET":
                self._param_set(t_ns, alanlar)
        elif yon == UAV2GCS:
            if msgname == "COMMAND_ACK":
                self._ack_alindi(t_ns, alanlar)
            elif msgname == "PARAM_VALUE":
                self._param_value(alanlar)
            elif msgname == "HEARTBEAT":
                self._heartbeat(t_ns, alanlar)

        if msgname.startswith("MISSION_"):
            self._gorev_mesaji(t_ns, yon, msgname, alanlar)


def komut_yanit_oznitelikleri(df: pd.DataFrame, t0_ns: int,
                              pencere_ns: int = PENCERE_NS) -> pd.DataFrame:
    """Bir uçuşun paketlerinden pencere başına 10 sütunu hesaplar.

    Dönen tablonun satırları pencere numarasıdır (0, 1, 2, ...), hiç olay
    olmayan pencereler de 0 değerleriyle bulunur. Süresi son pencerenin
    bitişinden sonra dolacak beklemeler sayılmaz: yanıt gelip gelmeyeceği
    bilinemez.
    """
    son_t_ns = int(df["t_ns"].max())
    hesaplayici = KomutYanitHesaplayici(t0_ns, pencere_ns)

    # Yalnızca ilgili mesajlar, zaman sırasıyla. "stable" sıralama aynı zaman
    # damgalı paketlerin kayıt sırasını korur.
    ilgili = df[df["msgname"].isin(ILGILI_MESAJLAR)].sort_values("t_ns", kind="stable")
    for t_ns, yon, msgname, alanlar_json in zip(
        ilgili["t_ns"], ilgili["direction"], ilgili["msgname"], ilgili["fields_json"]
    ):
        try:
            alanlar = json.loads(alanlar_json)
        except (TypeError, ValueError):
            continue  # çözülemeyen paket yok sayılır
        hesaplayici.paket_isle(int(t_ns), yon, msgname, alanlar)

    # Son pencerenin bitişine kadar süresi dolan beklemeleri de kapat. Son
    # paketten sonra dolanlar da dahildir: gerçek zamanlı gözlemci pencere
    # kapanırken bunları bilir, yani sonuç gelecekteki paketlere bağlı kalmaz.
    pencere_sayisi = (son_t_ns - t0_ns) // pencere_ns + 1
    hesaplayici.zaman_asimlarini_isle(t0_ns + pencere_sayisi * pencere_ns - 1)

    satirlar = []
    for pencere in range(pencere_sayisi):
        sayac = hesaplayici.sayaclar.get(pencere, Counter())
        gecikmeler = hesaplayici.gecikmeler_ms.get(pencere, [])
        satir = {sutun: int(sayac[sutun]) for sutun in SUTUNLAR[2:]}
        satir["ack_gecikme_ort_ms"] = sum(gecikmeler) / len(gecikmeler) if gecikmeler else 0.0
        satir["ack_gecikme_max_ms"] = max(gecikmeler) if gecikmeler else 0.0
        satirlar.append(satir)
    return pd.DataFrame(satirlar, columns=SUTUNLAR)
