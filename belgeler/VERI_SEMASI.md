# Veri Şeması (Ortak Sözleşme)

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

`flight_id`, `window_start_ns`, ardından öznitelik sütunları:

- `toplam_paket` — penceredeki toplam paket sayısı
- `n_<MSG>` — mesaj türüne göre sayılar (ör. `n_HEARTBEAT`, `n_COMMAND_LONG`)
- `farkli_sysid` — farklı sysid sayısı
- `seq_atlama`, `seq_tekrar` — sıra numarası atlama / tekrar sayısı
- `paket_arasi_ort_s`, `paket_arasi_std_s` — paketler arası sürenin ortalama/std'si
- `komut_sayisi` — komut mesajı sayısı

En sonda:

- `label` — `normal` veya pencerede baskın saldırı türü
- `attack_ratio` — penceredeki saldırı paketi oranı (0–1)

> `src_ip`, `src_port`, `raw_hex` bu dosyada **bulunmaz**. `oznitelik.py` bunu
> açıkça denetler ve bulursa hata verir.

## Pencere ve uçuş numarası (çakışmayı önler)

| Bilgisayar | `pc_id` | Uçuş aralığı | Örnek |
|-----------|---------|--------------|-------|
| 1. PC | `pc1` | F100–F199 | `F101_normal` |
| 2. PC | `pc2` | F200–F299 | `F205_spoof_cmd` |
| 3. PC | `pc3` | F300–F399 | `F312_flood` |

`pc_id` ve aralık `config.yaml`'da tutulur; her kişi yalnızca `pc_id`'yi ayarlar.
