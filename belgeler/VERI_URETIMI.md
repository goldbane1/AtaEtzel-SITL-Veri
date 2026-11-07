# Veri Üretimi — Uçtan Uca Oturum (VERI_URETIMI.md)

> 🧭 **Aşama 3–4 / 5** · [Yol haritası](../README.md#yol-haritası--neyi-hangi-sırayla) · Önceki → [KURULUM.md](KURULUM.md) · Sonraki → [VERI_PAYLASIMI.md](VERI_PAYLASIMI.md)

Bu rehber, bir veri üretim oturumunu baştan sona anlatır. Kaç terminal, hangi
sıra ile ne çalıştırılır ve hangi uçuşlar üretilir.

> **Ön koşul:** `python betikler/kontrol.py` hepsini TAMAM diyor olmalı.
> Her terminalde önce `source .venv/bin/activate` çalıştırın.

> **Uçuş numaraları:** Bu belgedeki örnekler (`F101_normal`, `F106_spoof_cmd`
> …) **pc1 numaralarıdır**. Siz kendi aralığınızdan numara kullanın; sıradaki
> boş adı şöyle öğrenin: `python betikler/ortak.py --sonraki normal`
> (saldırılı uçuşta `normal` yerine saldırı adı). Yanlış/kullanılmış numarada
> betik hiçbir şey başlatmadan durur. Ayrıntı:
> [UCUS_NUMARALARI.md](UCUS_NUMARALARI.md).

## Terminal düzeni

| Terminal | Ne çalışır |
|----------|-----------|
| 1 | SITL: `cd ~/ardupilot/ArduPlane && sim_vehicle.py -v ArduPlane --no-mavproxy` |
| 2 | Kayıt proxy'si + uçuş (yardımcı betikler bunu yönetir) |
| 3 | (Saldırılı uçuşta) saldırı betiği — yardımcı betik yönetir |

SITL **her zaman ayrı bir terminalde** ve sürekli açık kalır.

## 1) Normal uçuş

SITL açıkken, 2. terminalde:

```bash
bash betikler/normal_uretim.sh F101_normal gorevler/gorev1_dikdortgen.waypoints 180 3 90
#                               <ucus_id>   <gorev>                               sure ruzgar_hiz ruzgar_yon
```

Beklenen sonuç: `veri/ucuslar/F101_normal/` içinde dolu bir `paketler.parquet`
ve `meta.json`.

### Elle (üç terminal) yöntem

```bash
# Terminal 1
cd ~/ardupilot/ArduPlane && sim_vehicle.py -v ArduPlane --no-mavproxy
# Terminal 2
python betikler/kayit_proxy.py --ucus F101_normal
# Terminal 3
python betikler/ucus_yap.py --gorev gorevler/gorev1_dikdortgen.waypoints --ucus F101_normal --sure 180
```

## 2) Saldırılı uçuş

```bash
bash betikler/saldiri_uret.sh F106_spoof_cmd gorevler/gorev1_dikdortgen.waypoints spoof_cmd 180 30 60
#                             <ucus_id>       <gorev>                               <saldiri> sure saldiri_sure gecikme
```

`gecikme`, kalkış **doğrulandıktan sonra** sayılır (irtifa > 50 m ve AUTO'da waypoint
ilerlemesi). Kalkış olmazsa saldırı hiç başlamaz ve betik hata koduyla çıkar. Her
uçuştan önce SITL'yi yeniden başlatın: önceki uçuşun uçağı hâlâ havadadır.

`replay` için kaynak uçuş gerekir:

```bash
bash betikler/saldiri_uret.sh F108_replay gorevler/gorev2_uzunhat.waypoints replay 180 30 60 --kaynak-ucus F101_normal
```

Beklenen sonuç: uçuş klasöründe `ground_truth.json` (içinde `start_ns`/`end_ns`
dolu) ve parquet'te o aralıkta saldırgan adresinden paketler.

## Kanal bozulması

Üretim betikleri `KANAL_PROFIL` ve `KANAL_TOHUM` ortam değişkenlerini okur. Profiller
`config.yaml`'dadır:

| Profil | Gecikme | Kayıp |
|--------|---------|-------|
| `temiz` (varsayılan) | 0 | %0 |
| `hafif` | 20 ± 5 ms | %1 |
| `orta` | 80 ± 20 ms | %3 |
| `agir` | 200 ± 60 ms | %8 |

```bash
KANAL_PROFIL=orta KANAL_TOHUM=21 \
  bash betikler/normal_uretim.sh F110_normal gorevler/gorev2_uzunhat.waypoints 150 3 90
```

Bozulma duvarın konumuna göre uygulanır: Telsizden gelen paket (`gcs2uav`) önce bozulur
sonra kaydedilir, kaybolan paket kayıtta yoktur. Uçaktan çıkan paket (`uav2gcs`) önce
kaydedilir sonra bozulur, kaybolan paket kayıtta durur ama yer istasyonuna ulaşmaz. Bu
yüzden duvarın ölçtüğü ACK gecikmesi kanal gecikmesinden etkilenmez.

## Gece boyu toplu üretim

`toplu_uretim.py` uçuşları insansız, arka arkaya yapar. SITL'yi kendisi başlatıp kapatır,
ayrı terminalde açmayın. Başlamadan 5760 portunun boş olduğunu ve yeterli uçuş numarası
kaldığını denetler.

```bash
source .venv/bin/activate
python betikler/toplu_uretim.py --normal 40 --saldirili 40 \
    --kanal-profilleri temiz,hafif,orta --ana-tohum 1
```

| Parametre | Anlamı |
|-----------|--------|
| `--normal` | Normal uçuş sayısı |
| `--saldirili` | Saldırılı uçuş sayısı; türler dengeli dağılır |
| `--kanal-profilleri` | Virgülle profil listesi; dengeli dağılır |
| `--ana-tohum` | Aynı değer aynı planı üretir. **Her çalıştırmada ve makinede farklı verin** |
| `--no-isleme` | Sonda etiketleme, öznitelik ve doğrulamayı atlar |

Her uçuş için tohuma bağlı seçilenler: görev, rüzgâr (0–8 m/s, 0–359°), süre (180–300 sn),
telemetri hızı (2, 4, 8 Hz), irtifa farkı (−30…+50 m), kanal tohumu; saldırılı uçuşlarda
saldırı türü, alt türü, başlangıcı ve süresi. Saldırı, kalkış doğrulandıktan en az 16 sn sonra
başlar ve sonrasında en az 16 sn temiz kuyruk kalır. Hepsi `meta.json`'daki `toplu_plan`
alanına yazılır.

**Uçuşlar arasında SITL yeniden başlatılır.** Uçak bir önceki uçuştan havada kalır ve
yerinde reset rüzgâr, EKF ve görev durumunu taşıyabilir. Yeniden başlatma, saldırı uçağı
bozsa bile sonraki uçuşu temiz başlatır. `arduplane` her seferinde boş bir klasörde çalışır.

Bir uçuş başarısız olursa loglanır, `meta.json`'a `ucus_basarili: false` yazılır ve sıradakine
geçilir. Başarısız uçuşlar etiketleme, öznitelik ve bölmeye girmez; `dogrula.py` bunları ayrı
gösterir. Sonda özet tablo basılır.

Uçuş başı yaklaşık 5 dk sürer, gecede ~95 uçuş eder. `toplu_uretim.py` üretim boyunca uykuyu
`systemd-inhibit` ile engeller; WSL gibi ortamlarda engel alınamazsa uyarı verir. **Tek tek
çalıştırılan uçuşlarda** bu engel yoktur: Makinenin uykuya geçmediğinden siz emin olun.
Uykuya geçen uçuş başarısız sayılır, `dogrula.py` da kayıttaki boşluğu reddeder.

## 3) İşleme

```bash
python betikler/etiketle.py --hepsi      # her pakete label ekler
python betikler/oznitelik.py --hepsi     # pencereler.parquet üretir
python betikler/bol.py                   # veri/bolme.csv üretir
python betikler/dogrula.py --hepsi       # hepsi TAMAM olmalı
```

## Önerilen uçuş listesi (en az 5 + 5)

**Normal (5)** — farklı görev/rüzgâr/irtifa:

| Uçuş | Görev | Rüzgâr | Not |
|------|-------|--------|-----|
| `F101_normal` | gorev1_dikdortgen | 3 m/s @ 90° | dikdörtgen tur |
| `F102_normal` | gorev2_uzunhat | 0 | rüzgârsız, uzun bacak |
| `F103_normal` | gorev3_loiter | 5 m/s @ 180° | yüksek irtifa, görev içi loiter |
| `F104_normal` | gorev4_karisik | 4 m/s @ 45° | görev içi loiter ve iniş |
| `F105_normal` | gorev5_farkli | 6 m/s @ 270° | farklı yön |

Görevler `DO_JUMP` ile tekrar eder, kalkıştan sonra en az 300 sn AUTO'da kalır.

**Operatör komutları** her uçuşta varsayılan olarak açıktır; saldırılı uçuşlarda da.
Kalkış doğrulandıktan sonra, son 20 sn hariç, ortalama 20–40 sn'de bir rastgele:
AUTO → LOITER → AUTO, `DO_CHANGE_SPEED`, zararsız parametre okuma, `MISSION_SET_CURRENT`
ve mesaj hızı değişimi gönderilir; ayrıca periyodik durum sorguları yapılır. Bu sayede
model "komut = saldırı" diye ezberlemez. Sonuçlar `meta.json`'daki `operator_komutlari`
listesine yazılır. Aynı `--tohum` aynı planı üretir.

Betiklerde `ucus_yap.py`'ye ek ayar `UCUS_EK_ARG` ortam değişkeniyle verilir:

```bash
UCUS_EK_ARG="--tohum 42 --telemetri-hz 8 --irtifa-farki-m 30" \
  bash betikler/normal_uretim.sh F104_normal gorevler/gorev4_karisik.waypoints 300 4 45
```

`--no-operator-komut` operatör komutlarını kapatır. Veri üretiminde kapatmayın.

**Saldırılı (5)** — her saldırı bir uçuş:

| Uçuş | Saldırı | Görev | Örnek komut |
|------|---------|-------|-------------|
| `F106_spoof_cmd` | spoof_cmd | gorev1 | `... spoof_cmd 180 30 60` |
| `F107_impersonation` | impersonation | gorev2 | `... impersonation 180 40 50` |
| `F108_replay` | replay | gorev2 | `... replay 180 30 60 --kaynak-ucus F101_normal` |
| `F109_flood` | flood | gorev3 | `... flood 180 20 45 --hiz 300` |
| `F110_fake_telemetry` | fake_telemetry | gorev4 | `... fake_telemetry 180 30 50 --sapma-m 500` |

> Diğer makineler aynı listeyi kendi aralıklarıyla üretir (F2xx … F5xx).

## İpuçları

- `--speedup` **kullanmayın** (zamanlama bozulur).
- Port dolu hatası alırsanız: `pkill -f sim_vehicle; pkill -f kayit_proxy`.
- Her uçuştan sonra `dogrula.py --ucus <ucus_id>` ile hızlı kontrol yapın.
