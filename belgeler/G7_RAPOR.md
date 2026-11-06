# G7 Uçtan Uca Doğrulama Raporu

> 🧭 [Yol haritası](YOL_HARITASI.md) · Tarih: 2026-11-06 · Makine: pc1 masaüstü, Pop!_OS 24.04, Plane-4.7.2 (`fb773567`)

**Sonuç:** Üretim hattı gerçek SITL'de baştan sona çalışıyor. 4 uçuşun dördüne de `dogrula.py`
TAMAM dedi, 339 test geçti. Hat tam veri setini (G8) üretmeye hazır. Bu uçuşlar doğrulama
içindir; test uçuşları veri setine girmez.

## Uçuşlar

Hepsi `gorev1_dikdortgen`, 240 sn, operatör komutları açık.

| Uçuş | Tür | Kanal | Rüzgâr | Saldırı |
|------|-----|-------|--------|---------|
| `F123_normal` | Normal | `temiz` | 3 m/s @ 90° | — |
| `F124_spoof_cmd` | `spoof_cmd` | `temiz` | 3 m/s @ 90° | `mod_rtl`, tekrarlı, 77–107. sn |
| `F127_fake_telemetry` | `fake_telemetry` | `temiz` | 3 m/s @ 90° | 500 m sapma, 30 sn |
| `F126_normal` | Normal | `orta` | 3 m/s @ 90° | — |

`F125_fake_telemetry` geçersiz sayıldı ve yeniden uçuruldu (bkz. Bulgular).

## Paket sayısı ve yön dağılımı

| Uçuş | Toplam | `gcs2uav` | `uav2gcs` |
|------|--------|-----------|-----------|
| `F123_normal` | 31.733 | 271 | 31.462 |
| `F124_spoof_cmd` | 33.173 | 338 | 32.835 |
| `F127_fake_telemetry` | 32.282 | 421 | 31.861 |
| `F126_normal` | 31.935 | 269 | 31.666 |

## Etiket dağılımı

| Uçuş | `normal` | Saldırı | Gönderilen |
|------|----------|---------|------------|
| `F123_normal` | 31.733 | 0 | — |
| `F124_spoof_cmd` | 33.113 | 60 | 60 |
| `F127_fake_telemetry` | 32.131 | 151 | 151 |
| `F126_normal` | 31.935 | 0 | — |

Gönderilen her saldırı paketi doğru etiketlendi. Normal uçuşlarda saldırı etiketi yok.

## Pencere sayısının süreyle uyumu

| Uçuş | Kayıt süresi | Pencere | Beklenen | Boş pencere |
|------|--------------|---------|----------|-------------|
| `F123_normal` | 263,1 sn | 264 | 264 | 0 |
| `F124_spoof_cmd` | 262,8 sn | 263 | 263 | 0 |
| `F127_fake_telemetry` | 263,1 sn | 264 | 264 | 0 |
| `F126_normal` | 266,5 sn | 267 | 267 | 0 |

## Komut–yanıt öznitelikleri

Pencere başına ortalamalar. Saldırılı uçuşlarda aralık içi ve dışı ayrıdır.

| Sütun | `F123` normal | `F126` orta | `F124` içi | `F124` dışı | `F127` içi | `F127` dışı |
|-------|---------------|-------------|------------|-------------|------------|-------------|
| `ack_eslesme_sayisi` | 0,083 | 0,075 | **2,032** | 0,073 | 0,129 | 0,090 |
| `ack_gecikme_ort_ms` | 1,402 | 1,057 | 9,455 | 1,307 | 1,890 | 1,568 |
| `ack_gecikme_max_ms` | 1,459 | 1,088 | 10,483 | 1,387 | 1,890 | 1,623 |
| `yanitsiz_komut` | 0 | 0 | 0 | 0 | 0 | 0 |
| `eslesmeyen_ack` | 0 | 0 | 0 | 0 | 0 | 0 |
| `ack_red` | 0 | 0 | 0 | 0,004 | 0 | 0 |
| `gorev_protokol_ihlali` | 0 | 0 | 0 | 0 | 0 | 0 |
| `param_yanitsiz` | 0 | 0 | 0 | 0 | 0 | 0 |
| `mod_tutarsiz` | 0 | 0 | 0 | 0 | 0 | 0 |
| `komutsuz_mod_degisimi` | 0 | 0 | 0 | 0 | 0 | 0 |

`ack_gecikme_*` ortalamaları ACK'siz pencereleri 0 sayar. Yalnızca ACK içeren pencerelerde
ortalama gecikme: `F123` 19,5 ms, `F126` 14,9 ms, `F124` 13,0 ms, `F127` 18,4 ms.

Komutu kim, nasıl gönderdi öznitelikleri:

| Sütun | `F123` normal | `F126` orta | `F124` içi | `F124` dışı | `F127` içi | `F127` dışı |
|-------|---------------|-------------|------------|-------------|------------|-------------|
| `gcs_sysid_seq_bozulma` | 0,004 | 0,026 | **1,968** | 0,009 | 0,032 | 0,004 |
| `kritik_komut_sayisi` | 0,019 | 0,019 | **1,935** | 0,013 | — | — |
| `ayni_komut_tekrari` | 0 | 0 | **0,935** | 0 | — | — |
| `n_g2u_GLOBAL_POSITION_INT` | 0 | 0 | 0 | 0 | **4,839** | 0 |

Yorum:

- `spoof_cmd` uçağın modunu saldırının başladığı anda AUTO'dan RTL'ye aldı. Kabul edilen geçerli
  komut tutarsızlık üretmez: Tüm tutarsızlık sütunları 0 kaldı. Saldırıyı komutun gönderiliş biçimi
  gösteriyor (`gcs_sysid_seq_bozulma`, `kritik_komut_sayisi`, `ack_eslesme_sayisi`).
- `F124` dışındaki `ack_red` 0,004 tek pakettir: Operatörün `DO_CHANGE_SPEED` komutu, saldırının
  soktuğu RTL'de reddedildi. Hata değildir.
- `orta` kanal tutarsızlık sütunlarında yanlış alarm üretmedi.

**`spoof_cmd` varyant sınırı:** Bu uçuş tekrarlı ve `compid` 190'lı varyanttır. Toplu çalıştırmada
`F118` (`--taklit-compid`, `hafif`) `gcs_sysid_seq_bozulma` değerini 1,87 / 0,02 verdi, yani taklit
de yakalanıyor. `--tek-atis` varyantı (`--taklit-compid` ile tek komut) gerçek uçuşta denenmedi;
SITL'siz testte tek komut gönderdiği doğrulandı. MAVLink kimlik doğrulaması yapmadığı için doğru
kimlikli tek komut, paket içeriğinden ayırt edilemeyebilir. Bu sınırda asıl destek s1 kritik komut
kuralından ve s3 fiziksel tutarlılıktan gelmelidir. Değerlendirmede ayrı raporlanmalıdır.

## `fake_telemetry` yönü (K1)

Varsayım: Telsiz kanalı paylaşılan ortamdır, uçak telsizi menzildeyse sahte telemetriyi alıp duvara
iletir ([MIMARI.md](MIMARI.md)). Yönlü anten veya menzil dışı saldırgan bu varsayımı bozar.

- 151 saldırı paketinin tamamı `gcs2uav`, sysid 1, enjekte eden adresle kayıtlı.
- Paketler SITL'ye iletilmedi, yer istasyonuna ulaştı.
- 150 sahte konumun gerçek konumdan sapması 494–507 m (hedef 500 m).
- Bu saldırıda müdahale yalnızca uyarı ve panel bildirimidir; "gereksiz güvenli mod" metriği
  uygulanmaz.

## Ölçülen kanal gecikmesi ve kaybı

`F126_normal`, `orta` profil (80 ± 20 ms, %3):

| Yön | Gelen paket | Düşen | Ölçülen kayıp | Ölçülen gecikme |
|-----|-------------|-------|---------------|-----------------|
| `gcs2uav` | 275 | 6 | %2,18 | 80,4 ms |
| `uav2gcs` | 31.666 | 953 | %3,01 | 80,1 ms |

Duvar `gcs2uav`'yi gecikmeden sonra, `uav2gcs`'yi gecikmeden önce gördüğü için ölçülen ACK gecikmesi
kanal gecikmesinden etkilenmez. Bu, duvarın konumunun doğal sonucudur.

## Bulgular

1. **Makine uykuya geçti.** İlk `fake_telemetry` uçuşu (`F125`) havadayken sistem 19:44:32'de uykuya
   geçti, 21:36:25'te uyandı (`journalctl` ile doğrulandı). 6.711 sn boşluk oluştu, `meta.json` yine
   başarılı diyordu. Eklenenler: `toplu_uretim.py` uykuyu `systemd-inhibit` ile engelliyor,
   `ucus_yap.py` donmayı başarısız sayıyor, `dogrula.py` kayıttaki boşluğu reddediyor. `F125`
   başarısız işaretlendi ve aynı tohumla `F127` olarak yeniden uçuruldu.
2. **`F100` ve `F101`** G1'de düzeltilen geç damgalama hatasından önce üretildi, zaman damgaları
   güvenilir değildir. `dogrula.py` bunları yakalamıyor. Veri setine girmemelidir.
3. **Kalan açık kararlar:** K2 (ekip ve makine sayısı), K3 (numara bloğu). Test uçuşları
   masaüstü aralığında 28 numara kullandı.
