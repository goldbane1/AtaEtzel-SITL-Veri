# Yol Haritası (YOL_HARITASI.md)

> 🧭 **Görev takibinin tek doğru kaynağı** · [README](../README.md) · Asistan kuralları: [AGENTS.md](../AGENTS.md)

Sağlıklı uçuş ve veri kaydı için yapılacak işler burada, **sırayla** yürütülür.
Projenin güncel durumu bu dosyadan okunur: `[x]` olan bitmiştir, ilk `[ ]` olan
sıradaki görevdir.

## Nasıl çalışır?

Kullanıcı **"sıradaki görev"** dediğinde asistan:

1. Bu dosyadaki **ilk işaretlenmemiş** görevi yapar.
2. Tüm testleri çalıştırır (`pytest tests/`) ve kabul ölçütünü kontrol eder.
3. Ölçüt sağlandıysa kutucuğu `[x]` yapar, görevin **Sonuç** satırına tarihi ve
   kısa bir not yazar, Türkçe commit atar.
4. Durur ve kullanıcıya özet verir.

Kabul ölçütü sağlanmazsa kutucuk **işaretlenmez**; nedeni görevin **Sonuç**
satırına yazılır.

Kurallar:

- Tüm commitler `veri-duzeltmeleri` branch'ine gider.
- Her görev, SITL gerektirmeyen `tests/` testleri ekler.
- Bu dosyada listelenen şema değişiklikleri onaylanmıştır;
  [VERI_SEMASI.md](VERI_SEMASI.md) birlikte güncellenir. Listede olmayan şema
  değişikliği için kullanıcıya sorulur.
- **Dikkat** notları, görev yazılırken kod okunarak bulunan risklerdir.

## Özet

| Durum | Görev | Konu |
|-------|-------|------|
| [x] | G0 | Gerçek SITL'de duman testi |
| [x] | G1 | Komut–yanıt öznitelikleri |
| [x] | G2 | Boş pencereler |
| [x] | G3 | Normal uçuşa meşru operatör komutları |
| [x] | G4 | Sahte telemetri yönü |
| [x] | G5 | Yazma performansı |
| [x] | G6 | Kanal bozulması |
| [x] | G6.5 | Toplu üretim |
| [x] | G6.6 | Değerlendirme bölmeleri |
| [x] | G7 | Uçtan uca doğrulama |
| [ ] | G8 | Tam veri seti üretimi |

Bir görev bitince hem aşağıdaki kutucuğu hem bu tablodaki satırı `[x]` yapın.

## Açık kararlar

Asistanın kendi başına veremeyeceği kararlardır. İlgili göreve gelindiğinde karar
verilmemişse asistan görevi yapmadan önce kullanıcıya sorar.

| # | Karar | Etkilediği görev | Durum |
|---|-------|------------------|-------|
| K1 | **Duvar sahte telemetriyi görebiliyor mu?** Evet: Telsiz kanalı paylaşılan ortamdır, uçak telsizi menzildeyse paketi alıp duvara iletir (`MIMARI.md`, telsiz kanalı varsayımı). Paket duvarın gözünden `gcs2uav` kaydedilir | G4, G7, G8 | **Karar verildi** (2026-11-06) |
| K2 | **Ekip ve makine sayısı.** Ekip 4 kişi, 5 makine: Batuhan'ın 2 makinesi ile Şeyma, Hasan ve Yusuf'un laptopları (Ubuntu 26.04) | G8, `UCUS_NUMARALARI.md` | **Karar verildi** (2026-11-07) |
| K3 | **Numara bloğu.** Her makine kendi `pc_id`'sini alır: `pc1` Batuhan masaüstü, `pc2` Şeyma, `pc3` Hasan, `pc4` Yusuf, `pc5` Batuhan laptop. Her biri yüzlük blok, toplam 500 numara. Kod değişikliği gerekmez. Makine başına 60 uçuş planlanır, 40 numara yedek kalır | G6.5, G8 | **Karar verildi** (2026-11-07) |

---

## G0 — Gerçek SITL'de duman testi

- [x] **Durum**

**Amaç:** Kod bugüne kadar gerçek SITL'de hiç çalışmadı. Üzerine öznitelik
eklemeden önce uçağın gerçekten kalktığını ve verinin gerçekten aktığını görmemiz
gerekir. Kalkmayan bir uçuş, yerde duran uçağın verisini "normal uçuş" diye veri
setine sokar.

**Yapılacaklar:**

- `bash setup.sh` çalıştır, `python betikler/kontrol.py` hepsi TAMAM olsun.
- Tek bir 180 sn normal uçuş ve tek bir `spoof_cmd` uçuşu üret.
- `ucus_yap.py`'ye, uçağın gerçekten kalktığını (irtifa > 50 m, AUTO modunda
  waypoint ilerlemesi) uçuş sırasında HEARTBEAT ve GLOBAL_POSITION_INT ile
  doğrulayan bir kontrol ekle.
- Kalkış olmazsa uçuşu başarısız say ve `meta.json`'a yaz.
- Kalkış/AUTO akışında sorun çıkarsa düzelt ve `SORUN_GIDERME.md`'ye yaz.
- Saldırı gecikmesi script başlangıcından değil, **kalkış doğrulandıktan sonra**
  sayılsın. `ucus_yap.py` GPS beklediği için aksi hâlde saldırı uçak yerdeyken
  başlayabilir. `saldiri_uret.sh` kalkış başarısızsa saldırıyı hiç başlatmasın.

**Dikkat:**

- `ucus_yap.py` ACK beklemiyor, sabit 2 sn sonra AUTO'ya geçiyor ve GPS/EKF'in
  hazır olmasını beklemiyor; arm büyük ihtimalle reddedilir.
- Telemetri akışı (`REQUEST_DATA_STREAM` / `SET_MESSAGE_INTERVAL`) istenmiyor;
  `GLOBAL_POSITION_INT` hiç gelmeyebilir. Kalkış kontrolü buna bağlıdır.
- Görevlerin kalkış irtifası 100–150 m; 50 m eşiği beşinde de geçerlidir.
- `saldiri_uret.sh`, `ucus_yap.py`'nin hata kodunu yutuyor (`|| true`). Başarısız
  uçuş betiğin çıkış kodunda da görünmeli; G6.5 buna dayanır.

**Kabul ölçütü:**

- `kontrol.py` hepsi TAMAM.
- Normal ve `spoof_cmd` uçuşunun ikisinde de irtifa > 50 m ve AUTO'da waypoint
  ilerlemesi doğrulandı, sonuç `meta.json`'da.
- Kalkış olmayan bir uçuş `meta.json`'da başarısız görünüyor (SITL'siz testle
  doğrulanır).
- `spoof_cmd` uçuşunun saldırı başlangıcı kalkış doğrulamasından sonra.
- `dogrula.py` iki uçuşa da TAMAM diyor.

**Etkilenen dosyalar:** `betikler/ucus_yap.py`, `betikler/saldiri_uret.sh`,
`betikler/normal_uretim.sh`, `belgeler/SORUN_GIDERME.md`, `belgeler/VERI_SEMASI.md`
(`meta.json` alanları), `tests/`

**Sonuç:** 2026-11-06 — Tamamlandı. `kontrol.py` 7/7, `pytest` 15 test geçti. Masaüstünde
(`Plane-4.7.2`, `fb773567`) `F100_normal`: 24.502 paket, en yüksek irtifa 111,3 m.
`F101_spoof_cmd`: 24.783 paket, en yüksek irtifa 110,8 m, 60 saldırı paketi etiketlendi;
kalkış ~34. sn'de doğrulandı, saldırı 94. sn'de başladı. İkisine de `dogrula.py` TAMAM
dedi. Düzeltilenler: GCS HEARTBEAT el sıkışması, telemetri isteği, GPS/ön-arm beklemesi,
ACK denetimi, görev yükleme hatası, script çıkış kodları. Kalkış olmayan yol SITL'siz
testle doğrulandı. Gerçek uçuşta gözlenen açık noktalar: görev 1 ~79. sn'de bitip RTL'ye
geçiyor; `disarm` saldırısı uçuşta reddediliyor (ACK sonucu 4).

---

## G1 — Komut–yanıt öznitelikleri

- [x] **Durum**

**Amaç:** Mevcut öznitelikler paketleri yalnızca sayıyor. Bir saldırının izi çoğu
zaman komut ile yanıtı arasındaki ilişkide görülür: yanıtsız komut, istenmemiş
ACK, komutsuz mod değişimi. Model bu ilişkiyi görebilmeli.

**Yapılacaklar:** `betikler/komut_yanit.py` yaz:

- gcs2uav `COMMAND_LONG` / `COMMAND_INT` ↔ uav2gcs `COMMAND_ACK` eşleştirmesi
  (aynı `command`, 3 sn zaman aşımı).
- `MISSION_COUNT` → `REQUEST` → `ITEM` → `ACK` akış ihlalleri.
- `PARAM_SET` ↔ `PARAM_VALUE`.
- `SET_MODE` / `DO_SET_MODE` sonrası 3 sn içinde HEARTBEAT `custom_mode` değişimi
  ve komutsuz mod değişimi.
- Pencere sütunları: `ack_gecikme_ort_ms`, `ack_gecikme_max_ms`,
  `ack_eslesme_sayisi`, `yanitsiz_komut`, `eslesmeyen_ack`, `ack_red`,
  `gorev_protokol_ihlali`, `param_yanitsiz`, `mod_tutarsiz`,
  `komutsuz_mod_degisimi`.
- **Nedensellik:** Bir pencere yalnızca kendi bitişine kadarki veriyi kullanır;
  yanıtsız komut, zaman aşımının dolduğu pencerede sayılır.
- Sysid ile değil, yön + içerikle eşleştir.
- Dosya **bol yorumlu ve sade** yazılsın: Hasan okuyup anlayabilmeli (bkz.
  `MIMARI.md` 6. bölüm).

**Kabul ölçütü:**

- 10 sütun `pencereler.parquet`'te ve `VERI_SEMASI.md`'de.
- SITL'siz testler şunları kapsar: eşleşen/yanıtsız/eşleşmeyen ACK, reddedilen
  ACK, görev akışı ihlali, yanıtsız PARAM_SET, tutarsız ve komutsuz mod değişimi.
- Nedensellik testi: bir pencereden sonraki paketler silinince o pencerenin ve
  öncekilerin değerleri değişmiyor.
- Yanıtsız komut, gönderildiği pencerede değil zaman aşımının dolduğu pencerede
  sayılıyor.

**Etkilenen dosyalar:** `betikler/komut_yanit.py` (yeni), `betikler/oznitelik.py`,
`betikler/kayit_proxy.py`, `belgeler/VERI_SEMASI.md`, `belgeler/SORUN_GIDERME.md`,
`tests/`

**Sonuç:** 2026-11-06 — Tamamlandı. `pytest` 64 test geçti. 10 sütun `pencereler.parquet`'te
ve `VERI_SEMASI.md`'de; nedensellik her pencere sınırında testle doğrulandı. Gerçek veri
kayıtta bir hata gösterdi: `pymavlink` varsayılan modda SITL'nin başlangıç baytlarında
takılıyor, paketler saniyelerce geç damgalanıyordu. `robust_parsing` ile düzeltildi, regresyon
testi eklendi. Bu yüzden `F100` ve `F101` ilk saniyelerde güvenilir değildir, veri setine
girmez. Düzeltme sonrası: `F102_normal` (180 sn) ihlal, yanıtsız ve red sıfır; tek
`komutsuz_mod_degisimi` görev sonundaki meşru AUTO → RTL. SITL/gerçek saat oranı 0,99995.
`F103_spoof_cmd` (`mod_rtl`): mod saldırı anında RTL'ye geçti; 20 sahte komutun hepsi
kabul edildi. Sınır: Kabul edilen geçerli bir sahte komut tutarsızlık üretmez, yalnızca
`ack_eslesme_sayisi` artar (saldırıda 1,82, dışında 0,02/pencere). Boş pencereye düşen
olaylar G2'ye kadar tabloya girmez; bu dört uçuşta kayıp olmadı.

---

## G2 — Boş pencereler

- [x] **Durum**

**Amaç:** `oznitelik.py` şu an yalnızca paket içeren pencereleri üretiyor. Hiç
paket gelmeyen saniye, bir saldırının ya da bağlantı kopmasının izi olabilir ve
bugün veride tamamen kayboluyor. Zaman ekseni de kesintisiz olmalı.

**Yapılacaklar:**

- `oznitelik.py` ilk paketten son pakete kadar **her 1 sn için** pencere üretsin;
  boşsa sayımlar 0 olsun.
- Ek sütunlar: `bos_pencere`, `son_paketten_beri_s`, `saldiri_araliginda`,
  `saldiri_turu_aralik` (ground_truth aralığından).
- `dogrula.py` pencerelerin kesintisiz olduğunu kontrol etsin.
- **Yön bazlı öznitelikler** ekle (iki yön birlikte kullanılacağı için):
  `paket_gcs2uav`, `paket_uav2gcs`, her `SAYILACAK_MSGLER` türü için `n_g2u_<MSG>`
  ve `n_u2g_<MSG>`, yön başına `paket_arasi_ort_s` / `paket_arasi_std_s`.
  Mevcut sütunlar kalır.
- `SAYILACAK_MSGLER`'e ekle: `COMMAND_ACK`, `MISSION_COUNT`, `MISSION_REQUEST`,
  `MISSION_REQUEST_INT`, `MISSION_ACK`, `MISSION_CURRENT`, `PARAM_VALUE`.
- `seq_atlama` / `seq_tekrar` yön + `sysid` + `compid` akışı başına hesaplansın
  (seq her kaynak için ayrı işler) ve pencere sınırında önceki pencerenin son
  seq'iyle devam etsin; yalnızca geçmiş kullanıldığı için nedensellik bozulmaz.
- **Komutu kim, nasıl gönderdi öznitelikleri** ekle. G1'de kabul edilen geçerli sahte
  komutun tutarsızlık üretmediği görüldü. `F103`'te sahte akış kendi içinde kusursuzdu
  (compid 190), yalnızca sysid'e göre bakılınca 19 seq bozulması vardı:

  | Sütun | Açıklama |
  |-------|----------|
  | `gcs_akis_sayisi` | Penceredeki farklı gcs2uav `sysid` + `compid` akışı sayısı |
  | `gcs_sysid_seq_bozulma` | gcs2uav'de aynı `sysid` içinde, `compid` ayrımı yapmadan seq süreksizliği |
  | `ayni_komut_tekrari` | Pencerede aynı `command` değerinin tekrar sayısı (ilk geçiş hariç) |
  | `kritik_komut_sayisi` | Mod değişimi, disarm gibi kritik komut sayısı |
  | `komut_araligi_min_s` | gcs2uav komutları arasındaki en kısa süre; önceki pencereye taşınır, komut yoksa üst sınır değeri |

**Dikkat (veri sızıntısı):** `saldiri_araliginda` ve `saldiri_turu_aralik`
ground truth'tan gelir. Bunlar **etiket sütunudur, öznitelik değildir**; modele
girdi olarak verilmez. `VERI_SEMASI.md`'ye bu şekilde yazılır.

**Kabul ölçütü:**

- Boşluklu örnek veride pencere sayısı süreyle uyumlu, `window_start_ns` farkı her
  yerde tam 1 sn.
- Boş pencerede sayımlar 0 ve `bos_pencere` doğru.
- `dogrula.py` kesintili pencere dizisini EKSİK olarak bildiriyor (SITL'siz test).
- `saldiri_araliginda` / `saldiri_turu_aralik` ground truth aralığıyla tutarlı.
- Yön bazlı sayımların toplamı `toplam_paket` ile aynı; aynı mesaj türünün iki yönü
  ayrı sütunlarda görülüyor.
- İki farklı `compid` akışının karışması sahte `seq_atlama` üretmiyor; pencere
  sınırındaki seq atlaması sayılıyor.
- `gcs_sysid_seq_bozulma` iki akışın karışmasını yakalıyor; beş yeni sütun için
  nedensellik testi geçiyor, tekrar ve aralık değerleri örnek veride doğru.
- `VERI_SEMASI.md` yeni sütunları ve bunların etiket olduğunu yazıyor.

**Etkilenen dosyalar:** `betikler/oznitelik.py`, `betikler/dogrula.py`,
`belgeler/VERI_SEMASI.md`, `tests/`

**Sonuç:** 2026-11-06 — Tamamlandı. `pytest` 95 test geçti. `pencereler.parquet` 90 sütun;
4 test uçuşunda 750 pencere kesintisiz, boş değer yok, `dogrula.py` 4/4 TAMAM. `F103`'te
(`compid` 190, tekrarlı) `gcs_sysid_seq_bozulma` saldırıda 1,64, dışında 0,008/pencere;
`kritik_komut_sayisi` 1,82 ve 0,023. Normal uçuşta GCS'nin yeniden bağlanmasından gelen
tek seq süreksizliği beklenen davranıştır. Yeni pencereler `--ucus` ile tek uçuş
çalıştırılınca `pencereler.parquet`'in üzerine yazılır; toplu işlemde `--hepsi` kullanılır.

---

## G3 — Normal uçuşa meşru operatör komutları

- [x] **Durum**

**Amaç:** Normal uçuşlarda neredeyse hiç komut yoksa model "komut = saldırı"
ezberler. Meşru operatör trafiği olmalı ki model komutun varlığını değil,
tutarsızlığını öğrensin.

**Yapılacaklar:**

- `ucus_yap.py`'ye `--operator-komut` (varsayılan açık) ve `--tohum` ekle.
- Kalkıştan sonra, son 20 sn hariç, ortalama 20–40 sn'de bir rastgele: AUTO →
  LOITER → AUTO, `DO_CHANGE_SPEED`, zararsız PARAM okuma, `MISSION_SET_CURRENT`,
  mesaj hızı değişimi; ayrıca periyodik zararsız durum sorguları.
- Her komutun ACK sonucu beklenir.
- `meta.json`'a `operator_komutlari` listesi (`t_ns`, `komut`, `parametre`, `ack`)
  ve `tohum` yazılsın. Tohumla tekrar üretilebilir olsun.
- `ucus_yap.py`'ye `--telemetri-hz` ve `--irtifa-farki-m` ekle: telemetri akış hızı
  ve görev irtifası uçuş başına değişebilsin (görev dosyaları sabit kalır, fark
  yükleme sırasında uygulanır; kalkış eşiği 50 m'nin altına inilmez). İkisi de
  `meta.json`'a yazılsın.
- `belgeler/VERI_URETIMI.md`'deki önerilen uçuş listesini ve açıklamaları operatör
  komutlarına göre güncelle.
- F104 için yazan "mod değişimli" notunu düzelt (şu an görev dosyası yalnızca görev
  içi loiter ve iniş içeriyor).
- **Görevleri uzat:** 5 görev dosyası, kalkıştan sonra AUTO modunda en az 300 sn
  sürecek şekilde genişletilsin (daha uzak noktalar veya `DO_JUMP` ile tekrar).
  G0'da `gorev1` ~79. sn'de bitip uçuşun kalanı RTL'de geçti; bu hem normal uçuş
  çeşitliliğini düşürür hem saldırıların RTL sırasında düşmesine neden olur.

**Dikkat:**

- `MISSION_SET_CURRENT` kalkış ve iniş öğelerine atlamamalı, yoksa uçuş erken
  biter.
- Saldırılı uçuşlarda da operatör komutları varsayılan açık kalır; aksi hâlde model
  yine "komut = saldırı" öğrenir. `saldiri_uret.sh` ve `normal_uretim.sh` tohumu
  geçirmeli.

**Kabul ölçütü:**

- Aynı tohum aynı komut planını üretiyor, farklı tohum farklı plan (SITL'siz test).
- Plan son 20 sn'ye komut koymuyor; komut aralıklarının ortalaması 20–40 sn.
- Gerçek SITL uçuşunda `meta.json`'da `operator_komutlari` ve `tohum` var, her
  kaydın `ack` alanı dolu.
- Operatör paketleri `label = normal` kalıyor.
- `--irtifa-farki-m` görev noktalarına doğru uygulanıyor, ev konumuna ve iniş
  noktasına uygulanmıyor (SITL'siz test); `--telemetri-hz` meta'da görünüyor.
- `VERI_URETIMI.md` güncel, F104 notu düzeltilmiş.
- 5 görevin her biri gerçek SITL'de ölçüldü: kalkıştan sonra en az 300 sn AUTO'da
  kalıyor; ölçülen süreler **Sonuç** satırında.

**Etkilenen dosyalar:** `betikler/ucus_yap.py`, `betikler/normal_uretim.sh`,
`betikler/saldiri_uret.sh`, `gorevler/*.waypoints`, `belgeler/VERI_URETIMI.md`,
`belgeler/VERI_SEMASI.md` (`meta.json` alanları), `tests/`

**Sonuç:** 2026-11-06 — Tamamlandı. `pytest` geçti. 5 görevin hepsi gerçek SITL'de (345 sn,
operatör komutları açık) ölçüldü: AUTO'ya geçişten sonra 340 sn içinde hiçbiri görev sonuna
ulaşmadı, yani en az 300 sn şartı sağlandı.

| Uçuş | Görev | Rüzgâr | Hz | İrtifa farkı | Maks. irtifa | Operatör komutu |
|------|-------|--------|----|--------------|--------------|-----------------|
| `F104` | gorev1 | 3 | 4 | 0 | 110,8 | 32 |
| `F105` | gorev2 | 0 | 2 | +20 | 150,8 | 33 |
| `F106` | gorev3 | 5 | 8 | +50 | 210,7 | 31 |
| `F107` | gorev4 | 4 | 4 | −30 | 103,6 | 35 |
| `F108` | gorev5 | 6 | 8 | 0 | 140,9 | 31 |

Beş uçuşta `yanitsiz_komut`, `eslesmeyen_ack`, `ack_red`, `gorev_protokol_ihlali`,
`param_yanitsiz` ve `mod_tutarsiz` sıfır; tüm paketler `label = normal`. 3 `zaman_asimi`
kaydı `ALT_HOLD_RTL` parametresinin Plane-4.7.2'de olmamasındandı; `RTL_ALTITUDE` ile
düzeltildi, parametre adları kaynakla karşılaştıran test eklendi. Bu düzeltme uçuşla
yeniden denenmedi; G4 uçuşunda görülecek.

---

## G4 — Sahte telemetri yönü

- [x] **Durum**

**Amaç:** `fake_telemetry.py` şu an 14550'ye yazıyor; yani sahte telemetri uçağa da
gidiyor. Gerçekte bu saldırı yer istasyonunu kandırır, uçağı etkilememelidir. Paket
yine de duvarın gözünden telsizden gelir, bu yüzden `gcs2uav` kaydedilir.

**K1 kararı:** Telsiz kanalı paylaşılan ortamdır; uçak telsizi menzildeyse sahte
telemetriyi alıp duvara iletir, ek alıcı gerekmez. Duvar bu paketi uçaktan çıkarken
değil, telsizden gelirken görür. Yer istasyonunun almasını engelleyemez; müdahale
yalnızca uyarı ve panel bildirimidir (`MIMARI.md`).

**Yapılacaklar:**

- `kayit_proxy.py`'ye ikinci giriş: `hava_enjeksiyon_port` (`config.yaml`, 14551,
  yalnızca 127.0.0.1).
- Bu porta gelenler GCS adreslerine gider, SITL'ye **iletilmez** ve duvarın gözünden
  `direction=gcs2uav`, `src_ip`/`src_port` enjekte eden adres olarak kaydedilir.
- `fake_telemetry.py` bu porta yazsın; localhost kontrolü aynen kalsın.
- `dogrula.py`, `fake_telemetry` uçuşlarında saldırı paketlerinin `gcs2uav` yönünde ve
  sysid'inin uçağın kendi sysid'i olduğunu kontrol etsin.
- Her saldırının enjeksiyon yönünü README ve `VERI_SEMASI.md`'ye tablo olarak yaz;
  "duvarın gözünden yön" kavramını bir cümleyle açıkla.
- `fake_telemetry.py` sabit CMAC konumuna değil, **uçağın o anki gerçek konumuna**
  dayalı sahte değer üretsin (gerçek telemetriyi 14550 üzerinden okuyarak). `--sapma-m`
  küçük ve büyük değerlerle kullanılabilsin; sabit konum fazla kolay yakalanır.
- `time_boot_ms` gerçek akışla tutarlı olsun.

**Dikkat:**

- **Açık karar K1** bu görevin varsayımını belirler; göreve başlamadan sorulur.

- Enjeksiyon portu için ayrı bir MAVLink çözümleyici gerekir; yoksa seq takibi
  gerçek telemetriyle karışır.
- Saldırı betikleri `gonderen_kur` ile hep 14550'ye bağlanıyor; bu fonksiyon port
  almalı ve `localhost_dogrula` çağrısı korunmalı.
- `hava_enjeksiyon_port` soketi yalnızca 127.0.0.1'e bağlanır (bind).
- `config.yaml` makinelerde `skip-worktree` durumundadır (bkz.
  `UCUS_NUMARALARI.md`); git bu dosyadaki yeni alanı görmez ve `git pull` çakışabilir.
  Yeni alan commit'lenirken kişisel `ucus_no_araligi` değeri commit'e girmemeli.
  Ekibin yapacağı adım görev özetinde yazılmalı. Aynı durum G6 profilleri için de
  geçerlidir.

**Kabul ölçütü:**

- SITL'siz testte 14551'e gelen paket SITL tarafına gitmiyor, GCS'ye ulaşıyor,
  `gcs2uav` ve enjekte eden adresle kaydediliyor, etiketlemede `fake_telemetry` oluyor.
- `dogrula.py` yanlış yönlü ya da yanlış sysid'li `fake_telemetry` paketini EKSİK olarak
  bildiriyor.
- Localhost dışı hedef hâlâ reddediliyor.
- Yön tablosu README ve `VERI_SEMASI.md`'de.
- Sahte konum, verilen gerçek konuma `--sapma-m` kadar uzaklıkta (SITL'siz test).

**Etkilenen dosyalar:** `betikler/kayit_proxy.py`,
`betikler/saldirilar/fake_telemetry.py`, `betikler/saldirilar/saldiri_temel.py`,
`betikler/dogrula.py`, `config.yaml`, `README.md`, `belgeler/VERI_SEMASI.md`,
`tests/`

**Sonuç:** 2026-11-06 — Tamamlandı (K1 kararına göre). `pytest` 164 test geçti. `F109_fake_telemetry`
(150 sn): 76 saldırı paketi, tamamı `gcs2uav`, sysid 1, enjekte eden adresle; 75 sahte
konumun sapması 503–506 m. Normal uçuşlarda `n_g2u_GLOBAL_POSITION_INT` 0, saldırıda
4,69/pencere. `dogrula.py` 10/10 TAMAM. 14551'e yazan adres, kanal dinlemeyi temsil eden
telemetri kopyası alır, bu kopya kaydedilmez. `RTL_ALTITUDE` bu uçuşta okunmadı; adı kaynakla
testte doğrulandı, gerçek uçuşta G6.5 veya G7'de görülecek.

---

## G5 — Yazma performansı

- [x] **Durum**

**Amaç:** `kayit_proxy.py` her yazmada mevcut dosyayı okuyup baştan yazıyor. Dosya
büyüdükçe yazma yavaşlar ve bu sırada ana döngü durur; paket zaman damgaları bozulur,
yüksek hızlı flood sırasında kayıp olabilir.

**Yapılacaklar:**

- `kayit_proxy.py` pyarrow `ParquetWriter` ile akış hâlinde yazsın (açık şema,
  row group ekleme, kapanışta düzgün kapanış).
- Yazma ana döngüyü bloklamasın.
- SITL'siz performans testi: 60 sn, 500 paket/sn; döngü gecikmesinin ortalama ve
  p99'unu raporla.

**Dikkat:** `kill -9` veya elektrik kesintisinde `ParquetWriter` kapanmazsa dosya
**tamamen okunamaz**; eski yöntemde son yazıma kadarki veri kalıyordu. Gece boyu
üretimde (G6.5) önemlidir, görevde nasıl ele alındığı yazılmalıdır.

**Kabul ölçütü:**

- Performans testi çalıştı; ortalama ve p99 döngü gecikmesi raporlandı, sonuçlar
  **Sonuç** satırında.
- Masaüstünde ortalama döngü gecikmesi < 1 ms ve p99 < 5 ms. Bu eşik, Pi'deki
  20 ms'lik toplam hedefin (`MIMARI.md`) çoğunu modele bırakmak için konmuştur;
  ölçüm bunu sağlamıyorsa eşik kullanıcıya sorulmadan gevşetilmez.
- Eski ve yeni yöntemle yazılmış `paketler.parquet` dosyaları pandas ile aynı
  şekilde okunabiliyor (aynı sütunlar, aynı sırada, uyumlu tipler).
- Ctrl+C ve SIGTERM ile kapanışta dosya sağlam, tampondaki paketler kayıpsız.
- Beklenmedik sonlanmada ne olduğu test edildi ve belgelendi.
- Yazma kodu proxy'nin soket döngüsünden ayrı bir birimde; ileride güvenlik duvarı
  kararı aynı noktaya eklenebilir (`MIMARI.md` 5. bölüm).

**Etkilenen dosyalar:** `betikler/kayit_proxy.py`, `betikler/kayit_yazici.py` (yeni),
`betikler/proxy_performans.py` (yeni), `belgeler/SORUN_GIDERME.md`, `tests/`

**Sonuç:** 2026-11-06 — Tamamlandı. `pytest` 175 test geçti. 60 sn, 500 paket/sn ölçümü:
30.000 paketin hepsi kaydedildi; döngü gecikmesi ortalama 0,058 ms, p99 0,085 ms, en büyük
13,75 ms. Yazma ayrı iş parçacığında, ayrı dosyada (`kayit_yazici.py`). Eski ve yeni dosyalar
pandas ile birebir aynı okunuyor; gerçek `F102` verisiyle de doğrulandı. Ctrl+C ve SIGTERM
kapanışı kayıpsız. `kill -9` sonrası Parquet okunamıyor, ama her parti kurtarma günlüğüne de
yazıldığı için `--kurtar` testte 300 paketin 300'ünü geri getirdi; kayıp sınırı ~1 sn.

---

## G6 — Kanal bozulması

- [x] **Durum**

**Amaç:** Gerçek telsiz kanalı temiz değildir. Model yalnızca kusursuz kanalda
eğitilirse, gerçek gecikme ve kaybı saldırı sanar. Bozulma proxy içinde (netem
değil) ve tohumlu olursa üretim üç makinede de tekrar edilebilir.

**Yapılacaklar:**

- `--kanal-gecikme-ms`, `--kanal-jitter-ms`, `--kanal-kayip`, `--kanal-tohum`.
- `config.yaml`'da profiller:

  | Profil | Gecikme | Kayıp |
  |--------|---------|-------|
  | `temiz` | 0 | %0 |
  | `hafif` | 20 ± 5 ms | %1 |
  | `orta` | 80 ± 20 ms | %3 |
  | `agir` | 200 ± 60 ms | %8 |

- Üretim betikleri profil adı alsın.
- gcs2uav'de bozulma kayıttan **ÖNCE** (kaybolan paket kaydedilmez, iletilmez),
  uav2gcs'de kayıttan **SONRA** uygulanır.
- Bloklamayan zamanlanmış gönderim kuyruğu.
- `meta.json`'a `kanal` alanı.

**Dikkat:**

- Enjeksiyon paketleri (G4) `gcs2uav` kaydedilir, telsizden geldikleri için bozulma
  onlara da kayıttan önce uygulanır; kaybolan paket kaydedilmez ve GCS'ye gitmez.
- G7 "ölçülen gecikme ve kayıp" istiyor; bunun için `kanal` alanına sayaçlar da
  yazılmalı (ör. gönderilen, düşürülen, ölçülen ortalama gecikme).

**Kabul ölçütü:**

- SITL'siz testlerde ölçülen gecikme ve kayıp profil değerleriyle uyumlu.
- Aynı `--kanal-tohum` aynı düşürme kararlarını veriyor.
- gcs2uav'de kaybolan paket kayıtta yok, uav2gcs'de kaybolan paket kayıtta var.
- Gönderim kuyruğu ana döngüyü bloklamıyor.
- `temiz` profili paketleri değiştirmeden geçiriyor.
- `meta.json`'da `kanal` alanı var; profil adı, tohum ve ölçülen sayaçları içeriyor.
- Kanal kodu proxy'nin soket döngüsünden ayrı bir birimde.

**Etkilenen dosyalar:** `betikler/kayit_proxy.py`, `betikler/normal_uretim.sh`,
`betikler/saldiri_uret.sh`, `betikler/kanal.py` (yeni), `betikler/ucus_yap.py`, `config.yaml`,
`belgeler/VERI_SEMASI.md`, `belgeler/VERI_URETIMI.md`, `tests/`

**Sonuç:** 2026-11-06 — Tamamlandı. `pytest` 201 test geçti. Gerçek SITL ölçümleri:

| Uçuş | Profil | Yön | Paket | Gecikme | Kayıp |
|------|--------|-----|-------|---------|-------|
| `F110` | `orta` | gcs2uav | 178 | 80,4 ms | %1,1 |
| `F110` | `orta` | uav2gcs | 21.407 | 80,7 ms | %2,9 |
| `F111` | `agir` | gcs2uav | 206 | 197,8 ms | %6,3 |
| `F111` | `agir` | uav2gcs | 21.390 | 202,0 ms | %7,8 |

gcs2uav kayıp oranları paket sayısı az olduğu için hedeften oynuyor; SITL'siz 20.000 paketlik
testte profillerle uyumlu. Kanal açıkken p99 0,087 ms. `ucus_yap.py` kaybolan yanıtlar için
yeniden deneme kazandı; `agir` kanalda da kalkış, görev yükleme ve saldırı başarılı.
Gözlem: Duvar, gcs2uav'yi gecikmeden sonra ve uav2gcs'yi gecikmeden önce gördüğü için ACK
gecikmesi kanal gecikmesinden etkilenmez (`orta` 10,8 ms, `agir` 12,5 ms). Bu, duvarın
konumunun doğal sonucudur. Kanal kodu ayrı birimde: `kanal.py`.

---

## G6.5 — Toplu üretim

- [x] **Durum**

**Amaç:** Modelin yeterli veriye ulaşması için onlarca uçuş gerekir ve `--speedup`
kullanılamadığı için hepsi gerçek zamanlıdır. Üretim, insan başında durmadan gece
boyu çalışabilmeli; başarısız bir uçuş tüm geceyi yakmamalı.

**Yapılacaklar:**

- `betikler/toplu_uretim.sh` (veya `.py`). Parametreler: normal uçuş sayısı,
  saldırılı uçuş sayısı, kanal profili listesi, ana tohum.
- Her uçuş için tohuma bağlı olarak rastgele seçilsin: görev dosyası (5 görevden),
  rüzgâr hızı (0–8 m/s) ve yönü (0–359°), uçuş süresi (180–300 sn); saldırılı
  uçuşlarda saldırı türü, saldırı başlangıcı ve süresi.
- Saldırı türleri dengeli dağılsın.
- Uçuş adları `ortak.py --sonraki` ile alınsın, numara çakışma koruması atlanmasın.
- Uçuşlar arasında SITL'yi yeniden başlat (temiz durum) veya uçağı disarm edip
  başlangıç konumuna resetle; hangisini seçtiğini gerekçesiyle yaz.
- Bir uçuş başarısız olursa (G0'daki kalkış kontrolü) logla, `meta.json`'a yaz ve
  sonrakine geç; tüm döngü durmasın.
- Sonunda özet tablo: üretilen, başarısız, tür dağılımı, toplam süre.
- `VERI_URETIMI.md`'ye "gece boyu toplu üretim" bölümü ekle.
- `meta.json`'da başarısız işaretli uçuşlar işleme hattından (`etiketle`,
  `oznitelik`, `bol`) hariç tutulsun, `dogrula.py` raporunda ayrı gösterilsin.
- Normal uçuş çeşitliliği: tohuma bağlı olarak `--telemetri-hz` (2, 4, 8) ve
  `--irtifa-farki-m` (−30…+50 m) de seçilsin.
- Saldırı çeşitliliği: tohuma bağlı olarak alt türler de seçilsin: `spoof_cmd
  --komut`, `flood --hiz`, `impersonation --hiz`, `fake_telemetry --sapma-m` ve
  `--hiz`.
- **`spoof_cmd` etkili olsun:** `spoof_cmd.py`'nin varsayılan komutu uçuşu gerçekten
  etkileyen bir komut olsun (ör. `mod_rtl`). G0'da varsayılan `disarm` uçuşta
  reddedildi (ACK sonucu 4), uçak görevine devam etti. Toplu üretimde etkili komutlar
  ağırlıklı seçilsin; reddedilen `disarm` denemeleri azınlıkta kalsın.
- **`spoof_cmd` varyantları:** `--taklit-compid` (gerçek GCS ile aynı `sysid` +
  `compid`) ve `--tek-atis` (tek komut) eklensin; mevcut tekrarlı mod kalsın. Yanlış
  `compid` s1 beyaz listesine anında takılır ve saldırıyı fazla kolay gösterir. Seçilen
  varyant `ground_truth.json`'daki `params` alanına yazılsın.
- Replay kaynağı: aynı makinedeki, başarılı bir normal uçuştan tohumla seçilsin;
  uygun kaynak yoksa önce normal uçuşlar üretilsin.
- Saldırı zamanlaması: saldırı, kalkış doğrulandıktan **en az 16 sn sonra** başlasın
  ve bitişinden sonra **en az 16 sn** temiz kuyruk kalsın (RS-TCN son 16 pencereye
  bakar). Uçuş süresi buna yetmeyecekse saldırı süresi kısaltılsın.
- Tekrar üretilebilirlik: `meta.json`'a `ana_tohum`, `ucus_tohumu`, `kanal_tohumu`
  ve seçilen tüm parametreler yazılsın. Aynı ana tohum aynı uçuş planını üretsin.
- Başlamadan önce boş uçuş numarası sayısı denetlensin; yetmiyorsa betik hiç
  başlamadan Türkçe hata versin.

**Dikkat:**

- **Numara kapasitesi:** Uçuş başı ~5 dk ile 8 saatlik gece ~95 uçuş eder; masaüstü
  aralığı 50 uçuşta dolabilirdi; K3 ile makine başına 100 numara oldu.
- **Yeniden başlatma:** Ön tercih SITL'yi yeniden başlatmak (rüzgâr, EKF ve görev
  durumu temiz başlar). Bu durumda toplu betik SITL'yi kendisi başlatıp kapatmalı.
  Kesin seçim ve gerekçe görev sırasında yazılır.
- `--speedup` kullanılmaz; toplu betik de buna uyar.

**Kabul ölçütü:**

- 6 uçuşluk küçük bir toplu çalıştırma (4 normal, 2 saldırılı) insan müdahalesi
  olmadan bitsin ve `dogrula.py` hepsine TAMAM desin.
- Aynı ana tohum aynı uçuş planını üretiyor (SITL'siz test).
- Saldırı türleri dengeli; saldırı öncesi ve sonrası 16 sn temiz bölüm kuralı
  sağlanıyor (SITL'siz test ve `dogrula.py` kontrolü).
- Boş numara yetmediğinde betik başlamıyor.
- `spoof_cmd` varsayılan komutuyla gerçek SITL'de uçağın modu saldırı aralığında
  değişiyor.
- `--taklit-compid` paketlerinin `compid` değeri gerçek GCS ile aynı; `--tek-atis` tek
  komut gönderiyor (SITL'siz test).

**Etkilenen dosyalar:** `betikler/toplu_uretim.sh` veya `.py` (yeni),
`betikler/etiketle.py`, `betikler/oznitelik.py`, `betikler/bol.py`,
`betikler/dogrula.py`, `betikler/saldirilar/*.py`, `belgeler/VERI_URETIMI.md`,
`belgeler/VERI_SEMASI.md`, `tests/`

**Sonuç:** 2026-11-06 — Tamamlandı. Kabul çalıştırması (`--normal 4 --saldirili 2`, dört kanal
profili, ana tohum 1): 6 uçuş insansız 27 dk'da bitti, başarısız yok, `dogrula.py` hepsine TAMAM.
Ek çalıştırma (`--saldirili 5`, ana tohum 2): beş saldırı türü de gerçek uçuşta çalıştı, 21,5 dk,
başarısız yok. Toplam 23/23 uçuş TAMAM.

**Seçim: SITL yeniden başlatılır.** Gerekçe: Uçak önceki uçuştan havada kalır; reset rüzgâr, EKF
ve görev durumunu taşıyabilir. Yeniden başlatma temiz başlangıcı garanti eder, saldırı uçağı
bozsa bile sonraki uçuş etkilenmez. `arduplane` doğrudan, her uçuşta boş klasörde çalışır;
böylece EEPROM da temizdir, xterm gerekmez.

Saldırı imzaları (saldırı içi / dışı, pencere ortalaması): `spoof_cmd` taklit compid
`gcs_sysid_seq_bozulma` 1,87 / 0,02 ve mod AUTO → RTL; `replay` `gorev_protokol_ihlali` 18,4 / 0;
`flood` `toplam_paket` 417 / 63; `impersonation` `ayni_komut_tekrari` 5,5 / 0; `fake_telemetry`
`n_g2u_GLOBAL_POSITION_INT` aynı imza.

Çalıştırmalarda bulunan iki hata düzeltildi: `agir` kanalda telemetri isteği kaybolunca uçak
1 Hz'te kalıp `meta.json` yanlış oluyordu (istek 3 kez gönderiliyor, doğrulandı); gecikmeli son
saldırı paketleri `normal` etiketleniyordu (etikette 1 sn pay).

---

## G6.6 — Değerlendirme bölmeleri

- [x] **Durum**

**Amaç:** `bol.py` yalnızca saldırı türüne göre katmanlı tek bölme üretiyor.
Değerlendirme protokolünün T2, T3 ve T4 senaryoları için kanal profiline duyarlı
bölmeler ve eğitimde hiç görülmeyen koşullar gerekir (`MIMARI.md` 4. bölüm).

**Yapılacaklar:**

- `bol.py` katmanlamayı saldırı türü + kanal profiline göre yapsın (profil
  `meta.json`'daki `kanal` alanından okunur).
- Mevcut `veri/bolme.csv` (`flight_id`, `split`) ana bölme olarak kalsın; senaryo
  bölmeleri `veri/bolmeler/` altına ayrı dosyalar olarak yazılsın:
  - `T1`: Yalnızca `temiz` uçuşlar test edilir.
  - `T2`: Test, eğitimde görülen profillerden (`hafif`, `orta`).
  - `T3`: `agir` profili eğitim ve doğrulamadan tamamen çıkarılır, yalnızca testte
    bulunur.
  - `T4`: Her saldırı türü için ayrı dosya; o tür eğitim ve doğrulamadan tamamen
    çıkarılır, testte kalır.
- Her dosyada bir uçuş tek kümede olsun; örnek düzeyinde bölme yapılmasın.
- `VERI_SEMASI.md`'ye bölme dosyalarını ekle.

**Dikkat:** T5 (dış veri seti) bu reponun dışındadır; burada bölme üretilmez.
RS-TCN eğitimde yalnızca normal uçuşları seçer, karşılaştırma yöntemleri aynı
dosyaları kullanır.

**Kabul ölçütü:**

- Hiçbir uçuş bir bölme dosyasında birden fazla kümede değil (SITL'siz test).
- T3 eğitim ve doğrulamasında `agir` uçuş yok.
- T4'te çıkarılan tür eğitim ve doğrulamada yok, testte var.
- Yetersiz uçuş olduğunda Türkçe uyarı veriliyor.
- Aynı tohum aynı bölmeleri üretiyor.

**Etkilenen dosyalar:** `betikler/bol.py`, `belgeler/VERI_SEMASI.md`, `.gitignore`, `tests/`

**Sonuç:** 2026-11-06 — Tamamlandı. `pytest` 335 test geçti. `veri/bolmeler/` altına `T1`, `T2`, `T3` ve
beş `T4_<tür>` dosyası üretiliyor. Bir uçuş tek kümede; T3'te `agir` eğitim ve doğrulamada yok,
T4'te çıkarılan tür yalnızca testte; aynı tohum aynı bölmeyi veriyor. Gerçek 23 test uçuşunda
çalıştı; az uçuş olduğu için katman ve boş T2 test kümesi uyarıları beklenen davranıştır,
gerçek bölmeler G8'de üretilir. `bolme.csv` ve `bolmeler/` makineye özgü çıktı olduğu için git
dışında tutuldu.

---

## G7 — Uçtan uca doğrulama

- [x] **Durum**

**Amaç:** Tüm parçaların birlikte çalıştığını, gerçek SITL verisiyle ve ölçülmüş
sayılarla göstermek. Toplu üretime güvenmeden önceki son kapı budur.

**Yapılacaklar:**

- Tüm testleri çalıştır.
- SITL ile şu uçuşları üret: bir operatör komutlu normal, bir `spoof_cmd`, bir
  `fake_telemetry`, bir `orta` profilli normal.
- `etiketle` → `oznitelik` → `bol` → `dogrula`.
- Rapor `fake_telemetry` varsayımını yazar (K1); bu saldırıda "gereksiz güvenli mod"
  metriği uygulanmaz.
- `spoof_cmd` için öznitelik ortalamaları varyant başına ayrı verilsin. Doğru kimlikli
  tek komut varyantı paket içeriğinden ayırt edilemeyebilir: MAVLink kimlik doğrulaması
  yapmaz. Bu sınır raporda açıkça yazılsın; asıl destek s1 ve s3 katmanlarından gelir.
- Rapor: paket sayısı ve yön dağılımı, etiket dağılımı, pencere sayısının süreyle
  uyumu, komut–yanıt özniteliklerinin normal ve saldırılı uçuştaki ortalamaları,
  `fake_telemetry` yönü, ölçülen kanal gecikmesi ve kaybı.

**Kabul ölçütü:**

- Tüm testler geçti.
- 4 uçuşun hepsine `dogrula.py` TAMAM dedi.
- Rapor yukarıdaki maddelerin hepsini içeriyor.
- `fake_telemetry` saldırı paketlerinin tamamı `gcs2uav` ve uçağın sysid'iyle kayıtlı.
- Pencere sayısı uçuş süresiyle uyumlu.
- `orta` profilinde ölçülen gecikme ve kayıp 80 ± 20 ms, %3 değerleriyle uyumlu.

**Etkilenen dosyalar:** `belgeler/G7_RAPOR.md` (yeni),
`belgeler/YOL_HARITASI.md`; sorun çıkarsa ilgili betikler ve
`belgeler/SORUN_GIDERME.md`

**Sonuç:** 2026-11-06 — Tamamlandı. `pytest` 339 test geçti. Rapor: [G7_RAPOR.md](G7_RAPOR.md). 4 uçuşa
`dogrula.py` TAMAM dedi; pencere sayıları süreyle birebir uyumlu, saldırı paketlerinin tamamı
doğru etiketli. `fake_telemetry` 151 paketin tamamı `gcs2uav` ve uçağın sysid'iyle. `orta` kanalda
ölçülen 80,4 / 80,1 ms, %2,18 / %3,01. `F125` makine uykuya geçtiği için geçersiz sayıldı ve
yeniden uçuruldu (`F127`); uyku engeli ve donma kontrolleri eklendi.

---

## G8 — Tam veri seti üretimi

- [ ] **Durum**

**Amaç:** G7 hattın çalıştığını gösterir ama değerlendirme için gereken veriyi
üretmez. Hedef sayılar ve makineler arası birleştirme tanımlı olmadan veri seti
tamamlanmış sayılamaz.

**Yapılacaklar:**

- Üç 26.04 laptopta kurulum ve küçük deneme çalıştırması (`--normal 1 --saldirili 1`).
  **Yapıldı (2026-11-08):** Şeyma ve Hasan'ın logları incelendi (7/7 kontrol, 344 test, 2/2 uçuş);
  Yusuf'un denemesinin geçtiğini kullanıcı bildirdi.
- Deneme geçince `veri-duzeltmeleri`'ni `main`'e birleştir; herkes aynı commit'ten üretsin.
  **Yapıldı (2026-11-08).**
- Her makinede `pc_id` ve aralığı `UCUS_NUMARALARI.md` tablosuna göre ayarla. Masaüstündeki
  test uçuşları 2026-11-07'de silindi; diğer makinelerde test uçuşu varsa birleştirmeye alınmaz.
- Hedef hacmi üret (başlangıç önerisi, başlamadan kullanıcıyla kesinleştirilir):

  | Uçuş türü | Adet |
  |-----------|------|
  | Normal | 150 |
  | Her saldırı türü | 30 (toplam 150) |

  Her tür profillere dengeli dağılır (`temiz`, `hafif`, `orta`, `agir`). Uçuş başı
  ~4,5 dk ile toplam ~22,5 makine saatidir; 5 makinede makine başına 60 uçuş, ~4,5 saat.
- Tüm makinelerde `Plane-4.7.2` ve aynı repo commit'i kullanıldığını doğrula.
- Verileri `VERI_PAYLASIMI.md`'ye göre birleştir; numara tekrarı denetimini çalıştır.
- Birleştirme makinesinde `etiketle` → `oznitelik` → `bol` → `dogrula`.
- Rapor: tür × profil dağılımı, başarısız uçuş oranı, toplam uçuş saati, pencere
  sayısı, etiket dağılımı.

**Dikkat:** Normal uçuşların tamamı tek makineden gelirse model o makinenin
zamanlamasını öğrenebilir; uçuşlar makinelere dengeli dağıtılmalıdır.

**Kabul ölçütü:**

- Kesinleşen hedef sayılar başarılı uçuşlarla sağlandı.
- Birleşik veride numara tekrarı yok, `dogrula.py` tüm başarılı uçuşlara TAMAM dedi.
- Tüm uçuşların `meta.json`'ında tohum, görev, rüzgâr, kanal ve operatör komutları
  var.
- Değerlendirme bölmeleri birleşik veride üretildi, yetersiz uçuş uyarısı yok.
- Rapor hazır; ham veri git'e girmedi.

**Etkilenen dosyalar:** `belgeler/UCUS_NUMARALARI.md`, `belgeler/VERI_PAYLASIMI.md`,
ve rapor belgesi (yeni, yeri görevde belirlenir)

**Sonuç:** —
