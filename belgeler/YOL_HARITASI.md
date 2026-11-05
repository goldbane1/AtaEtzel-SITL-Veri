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
| [ ] | G0 | Gerçek SITL'de duman testi |
| [ ] | G1 | Komut–yanıt öznitelikleri |
| [ ] | G2 | Boş pencereler |
| [ ] | G3 | Normal uçuşa meşru operatör komutları |
| [ ] | G4 | Sahte telemetri yönü |
| [ ] | G5 | Yazma performansı |
| [ ] | G6 | Kanal bozulması |
| [ ] | G6.5 | Toplu üretim |
| [ ] | G6.6 | Değerlendirme bölmeleri |
| [ ] | G7 | Uçtan uca doğrulama |
| [ ] | G8 | Tam veri seti üretimi |

Bir görev bitince hem aşağıdaki kutucuğu hem bu tablodaki satırı `[x]` yapın.

## Açık kararlar

Asistanın kendi başına veremeyeceği kararlardır. İlgili göreve gelindiğinde karar
verilmemişse asistan görevi yapmadan önce kullanıcıya sorar.

| # | Karar | Etkilediği görev | Durum |
|---|-------|------------------|-------|
| K1 | **Duvar sahte telemetriyi görebiliyor mu?** Duvar uçak tarafında durur. Saldırgan telsizden yer istasyonuna yayın yaparsa paket duvardan geçmez. G4 bu paketleri proxy'de `uav2gcs` kaydettiği için duvarın telsiz kanalını dinlediğini varsayar. Bu varsayım geçerliyse `MIMARI.md`'ye yazılmalı; geçerli değilse `fake_telemetry` için tespit ve değerlendirme planı değişmeli | G4, G7, G8 | Bekliyor (Batuhan + Hasan) |
| K2 | **Ekip ve makine sayısı.** `MIMARI.md` iki kişi diyor; repo "üç kişi, üç makine" diyor. Üçüncü makine kimde, `pc3` kullanılacak mı? | G8, `UCUS_NUMARALARI.md` | Bekliyor |
| K3 | **Numara bloğu.** G8'in öneri hacmi (300 uçuş) üç yüzlük bloğu başarısız uçuşlara pay bırakmadan tam doldurur. `pc_blogu()` yüzlük bloğa sabit olduğu için ek blok kod değişikliği ister | G6.5, G8 | Bekliyor |

---

## G0 — Gerçek SITL'de duman testi

- [ ] **Durum**

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

**Sonuç:** —

---

## G1 — Komut–yanıt öznitelikleri

- [ ] **Durum**

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
`belgeler/VERI_SEMASI.md`, `tests/`

**Sonuç:** —

---

## G2 — Boş pencereler

- [ ] **Durum**

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
- `VERI_SEMASI.md` yeni sütunları ve bunların etiket olduğunu yazıyor.

**Etkilenen dosyalar:** `betikler/oznitelik.py`, `betikler/dogrula.py`,
`belgeler/VERI_SEMASI.md`, `tests/`

**Sonuç:** —

---

## G3 — Normal uçuşa meşru operatör komutları

- [ ] **Durum**

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

**Etkilenen dosyalar:** `betikler/ucus_yap.py`, `betikler/normal_uretim.sh`,
`betikler/saldiri_uret.sh`, `belgeler/VERI_URETIMI.md`, `belgeler/VERI_SEMASI.md`
(`meta.json` alanları), `tests/`

**Sonuç:** —

---

## G4 — Sahte telemetri yönü

- [ ] **Durum**

**Amaç:** `fake_telemetry.py` şu an 14550'ye yazıyor; yani sahte telemetri uçağa
gidiyor ve `gcs2uav` kaydediliyor. Gerçekte bu saldırı yer istasyonunu kandırır,
yönü `uav2gcs` olmalıdır. Yanlış yönlü veri modele yanlış imza öğretir.

**Yapılacaklar:**

- `kayit_proxy.py`'ye ikinci giriş: `hava_enjeksiyon_port` (`config.yaml`, 14551,
  yalnızca 127.0.0.1).
- Bu porta gelenler SITL'ye **iletilmez**, GCS adreslerine gider ve
  `direction=uav2gcs` olarak kaydedilir.
- `fake_telemetry.py` bu porta yazsın; localhost kontrolü aynen kalsın.
- `dogrula.py`, `fake_telemetry` saldırı paketlerinin `uav2gcs` olduğunu kontrol
  etsin.
- Her saldırının enjeksiyon yönünü README ve `VERI_SEMASI.md`'ye tablo olarak yaz.
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
  `uav2gcs` kaydediliyor ve etiketlemede `fake_telemetry` oluyor.
- `dogrula.py` yanlış yönlü `fake_telemetry` paketini EKSİK olarak bildiriyor.
- Localhost dışı hedef hâlâ reddediliyor.
- Yön tablosu README ve `VERI_SEMASI.md`'de.
- Sahte konum, verilen gerçek konuma `--sapma-m` kadar uzaklıkta (SITL'siz test).

**Etkilenen dosyalar:** `betikler/kayit_proxy.py`,
`betikler/saldirilar/fake_telemetry.py`, `betikler/saldirilar/saldiri_temel.py`,
`betikler/dogrula.py`, `config.yaml`, `README.md`, `belgeler/VERI_SEMASI.md`,
`tests/`

**Sonuç:** —

---

## G5 — Yazma performansı

- [ ] **Durum**

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

**Etkilenen dosyalar:** `betikler/kayit_proxy.py`, `tests/`

**Sonuç:** —

---

## G6 — Kanal bozulması

- [ ] **Durum**

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

- Enjeksiyon paketleri (G4) `uav2gcs` olduğu için bozulma onlara da kayıttan sonra
  uygulanır.
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
`betikler/saldiri_uret.sh`, `config.yaml`, `belgeler/VERI_SEMASI.md`,
`belgeler/VERI_URETIMI.md`, `tests/`

**Sonuç:** —

---

## G6.5 — Toplu üretim

- [ ] **Durum**

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
  aralığı `[100, 149]` 50 uçuşta dolar. Bkz. açık karar K3.
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

**Etkilenen dosyalar:** `betikler/toplu_uretim.sh` veya `.py` (yeni),
`betikler/etiketle.py`, `betikler/oznitelik.py`, `betikler/bol.py`,
`betikler/dogrula.py`, `betikler/saldirilar/*.py`, `belgeler/VERI_URETIMI.md`,
`belgeler/VERI_SEMASI.md`, `tests/`

**Sonuç:** —

---

## G6.6 — Değerlendirme bölmeleri

- [ ] **Durum**

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

**Etkilenen dosyalar:** `betikler/bol.py`, `belgeler/VERI_SEMASI.md`, `tests/`

**Sonuç:** —

---

## G7 — Uçtan uca doğrulama

- [ ] **Durum**

**Amaç:** Tüm parçaların birlikte çalıştığını, gerçek SITL verisiyle ve ölçülmüş
sayılarla göstermek. Toplu üretime güvenmeden önceki son kapı budur.

**Yapılacaklar:**

- Tüm testleri çalıştır.
- SITL ile şu uçuşları üret: bir operatör komutlu normal, bir `spoof_cmd`, bir
  `fake_telemetry`, bir `orta` profilli normal.
- `etiketle` → `oznitelik` → `bol` → `dogrula`.
- **Açık karar K1** sonuçlanmış olmalı; rapor `fake_telemetry` varsayımını yazar.
- Rapor: paket sayısı ve yön dağılımı, etiket dağılımı, pencere sayısının süreyle
  uyumu, komut–yanıt özniteliklerinin normal ve saldırılı uçuştaki ortalamaları,
  `fake_telemetry` yönü, ölçülen kanal gecikmesi ve kaybı.

**Kabul ölçütü:**

- Tüm testler geçti.
- 4 uçuşun hepsine `dogrula.py` TAMAM dedi.
- Rapor yukarıdaki maddelerin hepsini içeriyor.
- `fake_telemetry` saldırı paketlerinin tamamı `uav2gcs`.
- Pencere sayısı uçuş süresiyle uyumlu.
- `orta` profilinde ölçülen gecikme ve kayıp 80 ± 20 ms, %3 değerleriyle uyumlu.

**Etkilenen dosyalar:** rapor belgesi (yeni, yeri görevde belirlenir),
`belgeler/YOL_HARITASI.md`; sorun çıkarsa ilgili betikler ve
`belgeler/SORUN_GIDERME.md`

**Sonuç:** —

---

## G8 — Tam veri seti üretimi

- [ ] **Durum**

**Amaç:** G7 hattın çalıştığını gösterir ama değerlendirme için gereken veriyi
üretmez. Hedef sayılar ve makineler arası birleştirme tanımlı olmadan veri seti
tamamlanmış sayılamaz.

**Yapılacaklar:**

- Açık kararlar K2 ve K3'ü sonuçlandır, `UCUS_NUMARALARI.md`'yi güncelle.
- Hedef hacmi üret (başlangıç önerisi, başlamadan kullanıcıyla kesinleştirilir):

  | Uçuş türü | Adet |
  |-----------|------|
  | Normal | 150 |
  | Her saldırı türü | 30 (toplam 150) |

  Her tür profillere dengeli dağılır (`temiz`, `hafif`, `orta`, `agir`). Uçuş başı
  ~5 dk ile toplam ~25 makine saatidir.
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
gerekirse `betikler/ortak.py` (K3) ve rapor belgesi (yeni, yeri görevde belirlenir)

**Sonuç:** —
