# Veri Şeması (Ortak Sözleşme)

> 🧭 **Başvuru belgesi** (sıralı akışın parçası değil) · [Yol haritası](../README.md#yol-haritası--neyi-hangi-sırayla)

Tüm betikler **aynı dosya adlarını ve aynı sütunları** kullanır. Bu bölüm,
projedeki bütün parçaların dayandığı ortak sözleşmedir. Dosya/sütun adları
kendiliğinden değiştirilmez.

## Klasör yapısı

```
veri/
  ucuslar/
    F101_normal/
      paketler.parquet        # her iki yöndeki tüm paketler
      ham/flight.tlog         # MAVProxy tlog (isteğe bağlı)
      ham/sitl.BIN            # SITL DataFlash günlüğü (fizik referansı, isteğe bağlı)
      meta.json
    F106_spoof_cmd/
      paketler.parquet
      meta.json
      ground_truth.json       # yalnızca saldırılı uçuşlarda
  bolme.csv                   # flight_id, split
  oznitelikler/
    pencereler.parquet        # tüm uçuşların 1 sn'lik öznitelikleri
  ornek/                      # git'e giren çok küçük örnek (istisna)
```

## `paketler.parquet` sütunları

| Sütun | Tip | Açıklama |
|-------|-----|----------|
| `t_ns` | int64 | Alınma zamanı, nanosaniye (`time.time_ns()`) |
| `direction` | string | `gcs2uav` veya `uav2gcs` |
| `src_ip` | string | Gönderenin IP'si — **yalnızca etiketleme için** |
| `src_port` | int | Gönderenin portu — **yalnızca etiketleme için** |
| `sysid` | int | MAVLink sistem kimliği |
| `compid` | int | MAVLink bileşen kimliği |
| `seq` | int | Sıra numarası (0–255) |
| `msgid` | int | Mesaj türü numarası |
| `msgname` | string | Mesaj türü adı (HEARTBEAT, COMMAND_LONG…) |
| `length` | int | Paket uzunluğu (bayt) |
| `is_signed` | bool | İmzalı mı |
| `crc_ok` | bool | CRC doğru mu |
| `fields_json` | string | Çözümlenmiş alanlar (JSON) |
| `raw_hex` | string | Ham bayt (hex) — **yalnızca replay ve etiketleme için** |

> **KRİTİK KURAL — veri sızıntısı:** `src_ip`, `src_port` ve `raw_hex` **asla
> öznitelik olmaz**. Yalnızca etiketlemede ve replay saldırısında kullanılır.
> Modele verilirse model saldırıyı değil, saldırganın IP/portunu "ezberler".

Etiketlemeden sonra `paketler.parquet`'e bir de `label` sütunu eklenir
(`normal` veya saldırı türü).

## `meta.json` alanları

`flight_id`, `pc_id`, `ardupilot_version`, `vehicle` (ArduPlane), `mission_file`,
`wind` (hız/yön), `location`, `date`, `operator`, `duration_s`, `notes`.

`ucus_yap.py` uçuş sonunda şu alanları da yazar:

| Alan | Açıklama |
|------|----------|
| `ucus_basarili` | Kalkış doğrulandıysa `true`, değilse `false` |
| `basarisizlik_nedeni` | Başarısızlığın Türkçe nedeni; başarılı uçuşta `null` |
| `kalkis_kontrolu` | `dogrulandi`, `armed_goruldu`, `auto_goruldu`, `maks_irtifa_m`, `waypoint_ilerlemesi`, `son_gorev_sirasi` |

Kalkış doğrulaması için irtifa > 50 m ve AUTO modunda waypoint ilerlemesi gerekir.

## `ground_truth.json` (yalnızca saldırılı uçuşlar)

Bir uçuşta birden fazla saldırı olabileceği için kayıtlar bir **liste** olarak
tutulur:

```json
{
  "flight_id": "F106_spoof_cmd",
  "attacks": [
    {
      "attack_type": "spoof_cmd",
      "start_ns": 1730000000000000000,
      "end_ns":   1730000030000000000,
      "attacker_addr": "127.0.0.1:54321",
      "params": { "komut": "disarm", "sysid": 255 }
    }
  ]
}
```

`attack_type` şunlardan biridir: `spoof_cmd`, `impersonation`, `replay`, `flood`,
`fake_telemetry`.

## `pencereler.parquet` (1 sn'lik öznitelikler)

Pencereler **kesintisizdir**: İlk paketten son pakete kadar her saniye için tam bir
satır vardır (`window_start_ns` adımı tam 1 sn). Boş saniyede sayımlar 0 olur.

`flight_id`, `window_start_ns`, ardından öznitelik sütunları:

- `toplam_paket` — penceredeki toplam paket sayısı
- `paket_gcs2uav`, `paket_uav2gcs` — yön başına paket sayısı
- `bos_pencere` — pencerede hiç paket yoksa 1
- `son_paketten_beri_s` — pencere bitişinde son paketten beri geçen süre
- `n_<MSG>` — mesaj türüne göre sayılar (ör. `n_HEARTBEAT`, `n_COMMAND_ACK`)
- `n_g2u_<MSG>`, `n_u2g_<MSG>` — aynı sayılar yön başına
- `farkli_sysid` — farklı sysid sayısı
- `seq_atlama`, `seq_tekrar` — yön + sysid + compid akışı başına sıra numarası atlama /
  tekrar sayısı; pencere sınırında önceki pencereden devam eder
- `paket_arasi_ort_s`, `paket_arasi_std_s` — paketler arası sürenin ortalama/std'si
- `paket_arasi_ort_s_g2u`, `paket_arasi_std_s_g2u`, `paket_arasi_ort_s_u2g`,
  `paket_arasi_std_s_u2g` — aynı değerler yön başına
- `komut_sayisi` — komut mesajı sayısı

Komutu kim, nasıl gönderdi (`COMMAND_LONG`, `COMMAND_INT`, `SET_MODE`; gcs2uav):

- `gcs_akis_sayisi` — penceredeki farklı sysid + compid akışı sayısı
- `gcs_sysid_seq_bozulma` — aynı sysid içinde, compid ayrımı yapmadan seq süreksizliği
- `ayni_komut_tekrari` — aynı komutun tekrar sayısı (ilk geçiş hariç)
- `kritik_komut_sayisi` — mod değişimi, arm/disarm, RTL, iniş, görev başlatma gibi kritik
  komut sayısı
- `komut_araligi_min_s` — bir önceki komuttan geçen en kısa süre; önceki pencerelere de
  bakar, üst sınırı ve komutsuz pencere değeri 60 sn

Komut–yanıt tutarlılığı (`betikler/komut_yanit.py`). Eşleştirme sysid ile değil, yön +
içerikle yapılır; bir pencere yalnızca kendi bitişine kadarki veriyi kullanır.

| Sütun | Tip | Açıklama | Sayıldığı pencere |
|-------|-----|----------|-------------------|
| `ack_gecikme_ort_ms` | float | Eşleşen ACK'lerin ortalama gecikmesi; eşleşme yoksa 0 | ACK'in geldiği |
| `ack_gecikme_max_ms` | float | Eşleşen ACK'lerin en büyük gecikmesi; eşleşme yoksa 0 | ACK'in geldiği |
| `ack_eslesme_sayisi` | int | `COMMAND_LONG`/`INT` ile aynı `command` üzerinden eşleşen ACK sayısı | ACK'in geldiği |
| `yanitsiz_komut` | int | 3 sn içinde ACK gelmeyen komut sayısı | Zaman aşımının dolduğu |
| `eslesmeyen_ack` | int | Bekleyen komutu olmayan ACK sayısı (geç gelen ACK dahil) | ACK'in geldiği |
| `ack_red` | int | Sonucu kabul olmayan ACK sayısı (`IN_PROGRESS` hariç) | ACK'in geldiği |
| `gorev_protokol_ihlali` | int | `MISSION_COUNT` → `REQUEST` → `ITEM` → `ACK` akışına uymayan mesaj sayısı | Mesajın geldiği |
| `param_yanitsiz` | int | 3 sn içinde `PARAM_VALUE` gelmeyen `PARAM_SET` sayısı | Zaman aşımının dolduğu |
| `mod_tutarsiz` | int | `SET_MODE`/`DO_SET_MODE` sonrası 3 sn içinde istenen moda geçilmeyen istek sayısı | Zaman aşımının dolduğu |
| `komutsuz_mod_degisimi` | int | İstek olmadan gerçekleşen mod değişimi sayısı | Değişimin görüldüğü |

Notlar:

- Plane-4.7.2 `SET_MODE` mesajına `COMMAND_ACK` göndermez; bu yüzden `SET_MODE` için
  yalnızca mod değişimi izlenir.
- Reddedilen `DO_SET_MODE` için mod değişimi beklenmez, `mod_tutarsiz` sayılmaz.
- Görev sonunda RTL'ye geçiş gibi meşru otomatik değişimler de
  `komutsuz_mod_degisimi` sayılır; açılış modundan (`INITIALISING`) çıkış sayılmaz.

En sonda **etiket sütunları** gelir. Bunlar ground truth'tan türer, **modele girdi
olarak verilmez** (veri sızıntısı):

- `saldiri_araliginda` — pencere bir saldırı aralığıyla örtüşüyorsa 1
- `saldiri_turu_aralik` — en çok örtüşen saldırı türü, yoksa `normal`
- `attack_ratio` — penceredeki saldırı paketi oranı (0–1)
- `label` — `normal` veya pencerede baskın saldırı türü

`label` paket gerektirir; saldırı aralığındaki boş pencerede `normal` kalır, ama
`saldiri_araliginda` 1 olur.

> `src_ip`, `src_port`, `raw_hex` bu dosyada **bulunmaz**. `oznitelik.py` bunu
> açıkça denetler ve bulursa hata verir.

## Pencere ve uçuş numarası (çakışmayı önler)

| Bilgisayar | `pc_id` | Uçuş aralığı | Örnek |
|-----------|---------|--------------|-------|
| 1. PC | `pc1` | F100–F199 | `F101_normal` |
| 2. PC | `pc2` | F200–F299 | `F205_spoof_cmd` |
| 3. PC | `pc3` | F300–F399 | `F312_flood` |

`pc_id` ve aralık `config.yaml`'da tutulur; her cihaz **ikisini birlikte**
ayarlar. Aynı kişinin birden fazla cihazı varsa blok bölünür (ör. pc1 masaüstü
`[100, 149]`, laptop `[150, 199]`). Kurallar ve otomatik kontroller:
[UCUS_NUMARALARI.md](UCUS_NUMARALARI.md).
