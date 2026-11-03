# Veri Üretimi — Uçtan Uca Oturum (VERI_URETIMI.md)

> 🧭 **Aşama 3–4 / 5** · [Yol haritası](../README.md#yol-haritası--neyi-hangi-sırayla) · Önceki → [KURULUM.md](KURULUM.md) · Sonraki → [VERI_PAYLASIMI.md](VERI_PAYLASIMI.md)

Bu rehber, bir veri üretim oturumunu baştan sona anlatır. Kaç terminal, hangi
sıra ile ne çalıştırılır ve hangi uçuşlar üretilir.

> **Ön koşul:** `python betikler/kontrol.py` hepsini TAMAM diyor olmalı.
> Her terminalde önce `source .venv/bin/activate` çalıştırın.

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

`replay` için kaynak uçuş gerekir:

```bash
bash betikler/saldiri_uret.sh F108_replay gorevler/gorev2_uzunhat.waypoints replay 180 30 60 --kaynak-ucus F101_normal
```

Beklenen sonuç: uçuş klasöründe `ground_truth.json` (içinde `start_ns`/`end_ns`
dolu) ve parquet'te o aralıkta saldırgan adresinden paketler.

## 3) İşleme

```bash
python betikler/etiketle.py --hepsi      # her pakete label ekler
python betikler/oznitelik.py --hepsi     # pencereler.parquet üretir
python betikler/bol.py                   # veri/bolme.csv üretir
python betikler/dogrula.py --hepsi       # hepsi TAMAM olmalı
```

## Önerilen uçuş listesi (en az 5 + 5)

**Normal (5)** — farklı görev/rüzgâr/irtifa; biri operatör komutlu:

| Uçuş | Görev | Rüzgâr | Not |
|------|-------|--------|-----|
| `F101_normal` | gorev1_dikdortgen | 3 m/s @ 90° | temel |
| `F102_normal` | gorev2_uzunhat | 0 | rüzgârsız |
| `F103_normal` | gorev3_loiter | 5 m/s @ 180° | yüksek irtifa |
| `F104_normal` | gorev4_karisik | 4 m/s @ 45° | mod değişimli |
| `F105_normal` | gorev5_farkli | 6 m/s @ 270° | farklı yön |

**Saldırılı (5)** — her saldırı bir uçuş:

| Uçuş | Saldırı | Görev | Örnek komut |
|------|---------|-------|-------------|
| `F106_spoof_cmd` | spoof_cmd | gorev1 | `... spoof_cmd 180 30 60` |
| `F107_impersonation` | impersonation | gorev2 | `... impersonation 180 40 50` |
| `F108_replay` | replay | gorev2 | `... replay 180 30 60 --kaynak-ucus F101_normal` |
| `F109_flood` | flood | gorev3 | `... flood 180 20 45 --hiz 300` |
| `F110_fake_telemetry` | fake_telemetry | gorev4 | `... fake_telemetry 180 30 50 --sapma-m 500` |

> `pc2`/`pc3` kullanıcıları aynı listeyi kendi aralıklarıyla üretir (F2xx / F3xx).

## İpuçları

- `--speedup` **kullanmayın** (zamanlama bozulur).
- Port dolu hatası alırsanız: `pkill -f sim_vehicle; pkill -f kayit_proxy`.
- Her uçuştan sonra `dogrula.py --ucus <ucus_id>` ile hızlı kontrol yapın.
