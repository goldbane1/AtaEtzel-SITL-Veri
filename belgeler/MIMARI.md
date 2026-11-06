# Sistem Mimarisi (MIMARI.md)

> 🧭 **Başvuru belgesi** · [README](../README.md) · Görevler: [YOL_HARITASI.md](YOL_HARITASI.md)
>
> Bu repo yalnızca **veri üretir**, ama ürettiği veri aşağıdaki sisteme hizmet
> eder. Repodaki her değişiklik bu mimariye göre değerlendirilir.

## 1. Projenin bütünü

**Proje:** "Sabit Kanatlı İHA'lar için MAVLink Haberleşmesine Yönelik Yapay Zekâ
Destekli Siber Saldırı Tespit ve Müdahale Sistemi"

**Ekip:** Batuhan Özdemir ve Hasan Ümüt. Atatürk Üniversitesi Bilgisayar
Mühendisliği bitirme projesi. Ayrıca TÜBİTAK 2209-A başvurusu yapılıyor.

**Sorun:** MAVLink kaynak doğrulaması yapmaz, mesaj imzalama sahada çoğunlukla
kapalıdır. Telsiz kanalına erişen biri sahte komut gönderebilir, yer istasyonunu
taklit edebilir, eski paketleri tekrar oynatabilir, kanalı boğabilir veya operatöre
sahte telemetri gösterebilir.

**Çözüm:** Telsiz ile uçuş kontrolcüsü arasına, otopilota dokunmadan yerleşen,
Raspberry Pi üzerinde çalışan bir MAVLink güvenlik duvarı. `kayit_proxy.py` bu
güvenlik duvarının iskeletidir: bugün kaydediyor, ileride aynı noktada karar
verecek.

## 2. Güvenlik duvarı

```
 Yer istasyonu (GCS)            Saldırgan
         │                          │
         └────────────┬─────────────┘
                      ▼
                  [ TELSİZ ]
                      │
                      ▼
 ┌──────────────────────────────────────────────────────┐
 │        MAVLink GÜVENLİK DUVARI (Raspberry Pi)        │
 │                                                      │
 │   s1 Kural     s2 RS-TCN     s3 Fiziksel tutarlılık  │
 │       │            │                  │              │
 │       └────────────┼──────────────────┘              │
 │                    ▼                                 │
 │                 FÜZYON                               │
 │     (kesin kural ihlali skoru en üste çeker)         │
 │                    ▼                                 │
 │          KADEMELİ MÜDAHALE ───────► WEB PANELİ       │
 │    uyarı → engelleme → LOITER/RTL                    │
 └──────────────────────┬───────────────────────────────┘
                        ▼
                 [ OTOPİLOT ]
              (ArduPlane; dokunulmaz)
```

### s1 — Kural katmanı

Sysid/compid beyaz listesi, izin verilen mesaj türleri, mesaj sıklığı sınırı, seq
tutarlılığı, kritik komut listesi. Kesin ihlalde doğrudan yüksek skor.

### s2 — RS-TCN zaman serisi modeli (projenin özgün kısmı)

- **Girdi:** Son 16 adet 1 sn'lik pencerenin öznitelik dizisi (`oznitelik.py`
  çıktısı).
- **Yapı:** Nedensel, genişletilmiş evrişimli TCN; yalnızca geçmişe bakar.
- **Yarı denetimli:** Yalnızca **normal** uçuşlarla eğitilir, girdiyi yeniden
  oluşturmayı öğrenir. Saldırıda yeniden oluşturma hatası artar; hata, doğrulama
  uçuşlarına göre 0–1 arası kalibre şüphe skoruna çevrilir.
- **Ek bileşenler** (kademeli, ablasyonla ölçülecek): tahmin başlığı, Mahalanobis
  skoru, saldırı türünü belirleyip bilinmeyeni "bilinmeyen" diye işaretleyen
  prototip sınıflandırıcı.
- **Özgün öznitelikler:** Komut–yanıt tutarlılığı (COMMAND_ACK gecikmesi, yanıtsız
  komut, eşleşmeyen ACK, protokol durum ihlali). Literatürdeki çalışmalar (MUVIDS,
  GUIDE) yalnızca uçaktan gelen yöne bakıyor; biz iki yönü birlikte kullanıyoruz.

### s3 — Fiziksel tutarlılık

Komutlar ve telemetri değişimleri ArduPlane uçuş zarfıyla uyumlu mu (imkânsız konum
sıçraması, uçuşta motor durdurma vb.).

### Füzyon ve kademeli müdahale

Üç skor birleştirilir, kesin kural ihlalinde skor en üste çekilir. Müdahale
histerezisli eşiklerle kademelidir:

| Durum | Müdahale |
|-------|----------|
| Düşük şüphe | Operatöre uyarı, paket iletilir |
| Yüksek şüphe | Paket engellenir |
| Saldırı sürerse | LOITER veya RTL güvenli mod |

Amaç: Yanlış alarmlar görevi gereksiz yere sonlandırmasın.

**`fake_telemetry` istisnası:** Duvar, yer istasyonunun bu paketi almasını engelleyemez;
paket telsiz kanalından doğrudan yer istasyonuna ulaşır. Bu saldırıda müdahale yalnızca
uyarı ve panel bildirimidir, engelleme ve güvenli mod uygulanmaz.

**Web güvenlik paneli** skorları, alarmları, engellenen paketleri ve müdahaleleri
canlı gösterir.

### Telsiz kanalı varsayımı

Telsiz kanalı paylaşılan bir ortamdır. Saldırganın yer istasyonuna yolladığı sahte
telemetriyi, aynı kanal ve ağ ayarlarındaki uçak telsizi de menzildeyse alır ve seri
porttan duvara iletir. Ek bir alıcı gerekmez.

**Sınırlılık:** Yönlü anten kullanan ya da uçağın menzili dışındaki bir saldırgan bu
varsayımı bozar. Buna karşı yer istasyonu tarafında bir kontrol ileriki çalışmadır.

**Duvarın gözünden yön:** Paketin yönü hedefine göre değil, duvarın onu nereden
gördüğüne göre kaydedilir. Telsizden gelen her paket `gcs2uav`'dir; sahte telemetri de
yer istasyonunu hedeflese bile bu yönde görülür.

**Kural katmanı için aday kural (henüz kodlanmadı):** Telsizden gelen ve uçağın kendi
sysid'ini taşıyan paket şüphelidir.

## 3. Karşılaştırma yöntemleri

Isolation Forest, otomatik kodlayıcı, Random Forest, XGBoost ve MUVIDS benzeri LSTM
mesaj dizisi modeli. Hepsi aynı pencereler ve aynı bölmeyle değerlendirilir.

## 4. Değerlendirme protokolü

**Bölme:** Uçuş düzeyinde, yaklaşık %60/%20/%20; bir uçuş tek kümede. Örnek düzeyinde
bölme **yasak** (sızıntı).

| Senaryo | İçerik |
|---------|--------|
| T1 | Temiz ağ |
| T2 | Eğitim aralığında kanal bozulması |
| T3 | Eğitim aralığı **dışında** kanal bozulması |
| T4 | Leave-one-attack-out (bir saldırı türü eğitimden tamamen çıkarılır) |
| T5 | Dış veri seti |

**Metrikler ve hedefler:**

| Metrik | Hedef |
|--------|-------|
| Saldırı türü bazında duyarlılık, makro-F1 | ≥ 0,95 |
| Normal uçuşlarda yanlış alarm oranı | < %2 |
| Gereksiz güvenli mod geçişi (`fake_telemetry` için uygulanmaz) | 0 |
| Raspberry Pi'de paket başına gecikme (ortalama ve p99) | < 20 ms |
| Tespit gecikmesi | Ölçülür |

**İstatistik:** 5 rastgele tohum, bootstrap %95 güven aralığı, McNemar testi.

## 5. Bu repodan beklenen veri özellikleri

| Özellik | Neden önemli |
|---------|--------------|
| **Normal uçuş çeşitliliği** | Model yalnızca normal veriyle eğitilir; normalde görmediği her şeyi şüpheli sayar. Meşru operatör komutları ve farklı görev, rüzgâr, irtifa, telemetri hızları olmalı |
| **İki yön birlikte kayıt** | Komut–yanıt öznitelikleri buna dayanır |
| **Gerçek zamanlı damgalar** | `--speedup` yok, proxy döngüsü gecikme eklememeli; zamanlama öznitelikleri buna dayanır |
| **Kesintisiz pencereler** | TCN düzenli zaman serisi bekler; boş saniye de bilgidir |
| **Nedensel öznitelikler** | Model gerçek zamanlı çalışacak; bir pencere gelecekteki paketi kullanamaz |
| **Otomatik ve kesin etiket** | Saldırgan adresi + zaman aralığı. `src_ip`, `src_port`, `raw_hex` modele asla girmez |
| **Gerçekçi saldırı yönü** | Komut saldırıları uçağı, sahte telemetri yer istasyonunu hedefler. İkisi de telsizden geldiği için duvarın gözünden `gcs2uav` kaydedilir; sahte telemetri uçağa iletilmez |
| **Konuma göre kanal bozulması** | `gcs2uav` paketleri telsizden geçtikten sonra proxy'ye ulaşır, `uav2gcs` paketleri proxy'den çıktıktan sonra telsize girer. T2/T3 buna dayanır |
| **Tekrar üretilebilirlik** | Tohum, görev, rüzgâr, kanal profili ve operatör komutları `meta.json`'da |

**Kapsam sınırı:** Bu repo yalnızca veri üretir; model, füzyon, müdahale ve panel
kodu buraya **yazılmaz**. Ama proxy ileride güvenlik duvarına dönüşeceği için yapısı
(soket döngüsü, iki yön, enjeksiyon portları) temiz ve genişletilebilir tutulur.

## 6. Görev dağılımı

| Kişi | Sorumluluk |
|------|------------|
| **Batuhan** | SITL, kayıt proxy'si, saldırı senaryoları, kural katmanı, müdahale modülü, web paneli, Raspberry Pi |
| **Hasan** | Komut–yanıt öznitelikleri, RS-TCN, fiziksel tutarlılık katmanı, ablasyon, istatistiksel analiz |

Şu an repo işlerini Batuhan tek oturumda yürütüyor. `komut_yanit.py`'yi Hasan okuyup
anlayabilmeli; bu yüzden o dosya **bol yorumlu ve sade** yazılır.
