# G8 Tam Veri Seti Raporu

> 🧭 [Yol haritası](YOL_HARITASI.md) · Tarih: 2026-11-11 · Birleştirme makinesi: pc1 masaüstü ·
> ArduPlane Plane-4.7.2 (`fb773567`) · Üretim kodu: `d81610a`

**Sonuç:** 5 makinede 450 uçuş üretildi, hiçbiri başarısız olmadı. Birleşik veride numara tekrarı
yok, `dogrula.py` 450 uçuşun hepsine TAMAM dedi. 118.942 pencere çıkarıldı ve 8 değerlendirme
senaryosunun hiçbirinde test kümesi boş kalmadı. Veri seti model eğitimine hazır.

## Üretim

Her makine `toplu_uretim.py --normal 40 --saldirili 50 --kanal-profilleri temiz,hafif,orta,agir
--ana-tohum 10N --no-isleme` ile 90 uçuş üretti. Etiketleme ve sonraki adımlar birleşik veride pc1'de
yapıldı. Komutlar: [G8_AGENT_KOMUTLARI.md](G8_AGENT_KOMUTLARI.md).

| `pc_id` | Makine | Uçuşlar | Ana tohum | Başarılı | Başarısız | Üretim süresi |
|---------|--------|---------|-----------|----------|-----------|---------------|
| pc1 | Batuhan masaüstü | F100–F189 | 101 | 90 | 0 | 382,4 dk |
| pc2 | Şeyma laptop | F200–F289 | 102 | 90 | 0 | 398,6 dk |
| pc3 | Hasan laptop | F300–F389 | 103 | 90 | 0 | 408,1 dk |
| pc4 | Yusuf laptop | F400–F489 | 104 | 90 | 0 | 402,2 dk |
| pc5 | Batuhan laptop | F500–F589 | 105 | 90 | 0 | 393,0 dk |
| **Toplam** | | **450** | | **450** | **0** | **1.984 dk (~33,1 saat)** |

- **Başarısız uçuş oranı:** %0.
- **Toplam uçuş süresi** (`meta.json` `duration_s`): 33,0 saat. Uçuş başına ortalama ~4,4 dk.
- **Aynı kod:** Her makinenin 90 uçuşu, `uretim_plani(40, 50, profiller, 10N)` ile yeniden üretilen
  planla tür, görev, süre, kanal profili ve uçuş tohumu bakımından birebir uyuşuyor (0 fark).
  Plan kodu her makinede aynıdır. Sürüm her `meta.json`'da `Plane-4.7.2`.
- **Aktarım:** Dört arşivin sha256 değeri tuttu. Arşivler üzerine yazılmadan açıldı; yollar yalnızca
  `ucuslar/` altında, numaralar kendi aralığında.

## Tür × kanal profili dağılımı

| Tür | `temiz` | `hafif` | `orta` | `agir` | Toplam |
|-----|---------|---------|--------|--------|--------|
| normal | 50 | 50 | 50 | 50 | 200 |
| spoof_cmd | 10 | 11 | 14 | 15 | 50 |
| impersonation | 13 | 13 | 11 | 13 | 50 |
| replay | 13 | 14 | 12 | 11 | 50 |
| flood | 13 | 12 | 12 | 13 | 50 |
| fake_telemetry | 12 | 12 | 12 | 14 | 50 |

Profiller her türün içinde dengeli dağıtıldı (2026-11-08 düzeltmesi). Düzeltmeden önceki planda
`spoof_cmd + temiz` hücresine 300 uçuşta yalnızca 1 uçuş düşüyordu.

**Çeşitlilik:** Görev `gorev1` 71, `gorev2` 108, `gorev3` 87, `gorev4` 82, `gorev5` 102 uçuş.
Telemetri hızı 2 Hz 144, 4 Hz 141, 8 Hz 165 uçuş. Normal ve saldırılı uçuşlarda toplam 9.254 meşru
operatör komutu var.

## Paketler

| | Adet |
|-|------|
| Toplam paket | 17.581.488 |
| `uav2gcs` | 17.085.575 |
| `gcs2uav` | 495.913 |

| Paket etiketi | Adet |
|---------------|------|
| normal | 17.205.696 |
| flood | 333.129 |
| replay | 16.797 |
| impersonation | 16.555 |
| fake_telemetry | 7.362 |
| spoof_cmd | 1.949 |

## Pencereler

`veri/oznitelikler/pencereler.parquet`: 118.942 pencere, uçuş başına ortalama 264,3, 90 sütun.
`dogrula.py` tüm uçuşların pencerelerinin kesintisiz ve süreyle uyumlu olduğunu doğruladı.

| Küme (uçuş) | normal | spoof_cmd | impersonation | replay | flood | fake_telemetry |
|-------------|--------|-----------|---------------|--------|-------|----------------|
| eğitim (270) | 67.031 | 606 | 884 | 891 | 808 | 804 |
| doğrulama (90) | 22.598 | 173 | 342 | 301 | 295 | 250 |
| test (90) | 22.571 | 247 | 217 | 258 | 271 | 395 |
| **Toplam** | **112.200** | **1.026** | **1.443** | **1.450** | **1.374** | **1.449** |

Bu tablo temel bölmedir (`bolme.csv`, %60/%20/%20, uçuş düzeyinde). Senaryolarda `agir` eğitim
dışındadır.

## Değerlendirme senaryoları

`veri/bolmeler/` altında 8 senaryo. Eğitimde `agir` hariç 90 normal uçuş var. Test kümesindeki
uçuş sayıları:

| Senaryo | normal | spoof_cmd | impersonation | replay | flood | fake_telemetry |
|---------|--------|-----------|---------------|--------|-------|----------------|
| T1 (temiz) | 10 | 2 | 2 | 2 | 2 | 3 |
| T2 (hafif, orta) | 20 | 5 | 4 | 6 | 6 | 6 |
| T3 (agir) | 50 | 15 | 13 | 11 | 13 | 14 |
| T4_<tür> | 30 | dışarıda bırakılan türün 50 uçuşu + diğer türlerden 6–9 | | | | |

`bol.py` yetersiz uçuş uyarısı vermedi.

## Kabul ölçütü

| Ölçüt | Durum |
|-------|-------|
| Hedef sayılar başarılı uçuşlarla sağlandı (200 normal, tür başına 50) | ✓ |
| Birleşik veride numara tekrarı yok, `dogrula.py` tüm başarılı uçuşlara TAMAM | ✓ 450/450 |
| Tüm `meta.json`'larda tohum, görev, rüzgâr, kanal ve operatör komutları var | ✓ eksik alan 0 |
| Değerlendirme bölmeleri birleşik veride üretildi, yetersiz uçuş uyarısı yok | ✓ |
| Rapor hazır, ham veri git'e girmedi | ✓ |

`pytest tests/`: 345 test geçti.

## Sınırlar ve modele notlar

- **T1 küçük:** Temiz kanal testinde tür başına 2–3 uçuş var. Tür bazında duyarlılık ve güven
  aralıkları T1 ve T2 birlikte raporlanırsa daha sağlam olur.
- **spoof_cmd en az pencereye sahip tür (1.026):** Doğru kimlikli tek atış varyantı paket
  içeriğinden ayırt edilemeyebilir (G7 raporu). Bu türde asıl destek s1 ve s3 katmanlarından gelir.
- **Veri tamamen SITL'dir.** Gerçek uçuşa genelleme T5 (dış veri seti) ile ayrıca ölçülmelidir.
- Ham veri ve arşivler git dışındadır. Arşivler birleştirme makinesinde yedek olarak tutulur.
