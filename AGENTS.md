# AGENTS.md — Yapay zekâ asistanları için proje rehberi

> Bu dosya, bu repoyu açan **her kodlama asistanı** (Claude Code, Codex, Cursor,
> Copilot, Gemini CLI vb.) için yazılmıştır. Claude Code bunu `CLAUDE.md`
> üzerinden otomatik okur. İnsanlar için giriş noktası `README.md`'dir.

## 1. Proje nedir?

**AtaEtzel** ekibinin bitirme projesi: *"Sabit Kanatlı İHA'lar için MAVLink
Haberleşmesine Yönelik Siber Saldırı Tespit ve Müdahale Sistemi"*.

Bu repo bütünün yalnızca **veri üretimi** kısmıdır:

1. ArduPlane SITL'de **normal** ve (yalnızca simülasyon içi, localhost)
   **saldırılı** uçuşlar üretilir.
2. MAVLink trafiği bir **kayıt proxy'si** (`betikler/kayit_proxy.py`) ile iki
   yönde kaydedilir → `paketler.parquet`.
3. Paketler etiketlenir, 1 sn'lik öznitelik pencereleri çıkarılır, uçuş
   düzeyinde eğitim/doğrulama/test bölmesi yapılır.

Amaç: ileride eğitilecek **savunma amaçlı** bir saldırı tespit (IDS) / MAVLink
güvenlik duvarı modeli için etiketli veri seti. Model ve panel bu reponun
**dışındadır**.

5 saldırı türü: `spoof_cmd`, `impersonation`, `replay`, `flood`, `fake_telemetry`.

**Bütün mimari:** Üretilen veri, telsiz ile otopilot arasına yerleşen Raspberry Pi
tabanlı üç katmanlı bir güvenlik duvarını (kural, RS-TCN, fiziksel tutarlılık;
füzyon ve kademeli müdahale) eğitmek ve değerlendirmek için kullanılır.
`kayit_proxy.py` bu duvarın iskeletidir. Yapılan her değişiklik bu mimariye göre
değerlendirilir: [`belgeler/MIMARI.md`](belgeler/MIMARI.md).

## 2. İletişim kuralları

- **Her şey Türkçe**: kullanıcıyla konuşma, kod yorumları, log/hata mesajları,
  belgeler, commit mesajları.
- Ekip öğrenci; açıklamaları **sade ve adım adım** yap, teknik terimleri kısaca
  aç. Komut önerirken ne işe yaradığını bir cümleyle söyle.
- Değişken/fonksiyon adları da Türkçe (ASCII) tutulur: `ucus_klasoru`,
  `config_oku`, `localhost_dogrula` … Mevcut stile uy.

## 3. Değişmez kurallar (çiğneme!)

1. **Güvenlik / etik:** Saldırı betikleri yalnızca `127.0.0.1`'e bağlanır.
   `betikler/ortak.py` içindeki `localhost_mu` / `localhost_dogrula` kontrolü
   **silinmez, gevşetilmez, atlanmaz**. Dış ağa veya gerçek araca saldıran kod
   yazılmaz. Bu bir savunma projesidir.
2. **ArduPlane sürümü sabit: `Plane-4.7.2`.** Tüm makinelerde aynı etiket olmalı;
   sürüm yükseltme önerme.
3. **Ham veri git'e girmez:** `*.parquet`, `*.tlog`, `*.BIN`, `veri/ucuslar/`,
   `veri/oznitelikler/` (`.gitignore`'da). İstisna: `veri/ornek/` altındaki
   çok küçük örnekler.
4. **`--speedup` kullanılmaz** (zaman damgaları/öznitelikler gerçek zamana göre).
5. **Veri şeması sözleşmedir:** `belgeler/VERI_SEMASI.md`'deki dosya ve sütun
   adları kendiliğinden değiştirilmez. Değişiklik gerekiyorsa önce kullanıcıya
   sor, sonra şema belgesini + tüm betikleri birlikte güncelle.
   **Not:** `belgeler/YOL_HARITASI.md`'de listelenen şema değişiklikleri
   onaylanmıştır; `VERI_SEMASI.md`'yi birlikte güncelle. Listede olmayan şema
   değişikliği için yine sor.
6. **Veri sızıntısı:** `src_ip`, `src_port`, `raw_hex` **asla öznitelik
   olmaz** (`oznitelik.py`'ye eklenmez). Yalnızca etiketleme ve replay içindir.
7. `config.yaml`'da her makine yalnızca `pc_id` ve `ucus_no_araligi`'nı
   değiştirir; diğer alanlar tüm makinelerde aynı kalır.

## 4. Mimari (kısaca)

```
GCS (ucus_yap.py / MAVProxy) ─┐
                              ├─ UDP 14550 ─> [kayit_proxy.py] ─ TCP 5760 ─> ArduPlane SITL
Saldırı betikleri (localhost)─┘          (her paketi kaydeder)
```

- `gcs2uav`: 14550'ye gelen paket → SITL'ye iletilir. Yön duvarın gözündendir.
- Havadan enjeksiyon: 14551'e gelen paket → yer istasyonuna gider, SITL'ye gitmez,
  `gcs2uav` kaydedilir (sahte telemetri).
- `uav2gcs`: SITL telemetrisi → 14550'ye yazmış tüm adreslere geri döner.
- Saldırgan ile meşru GCS'yi etiketlemede ayıran şey `src_ip:src_port`
  (`ground_truth.json` içindeki `attacker_addr`) + zaman aralığıdır.

## 5. Dosya haritası

| Yol | Görevi |
|-----|--------|
| `config.yaml` | pc_id, uçuş aralığı, portlar, veri klasörü |
| `setup.sh` | Baştan sona kurulum (ArduPilot `~/ardupilot`'a, `.venv`) |
| `betikler/ortak.py` | Ortak yardımcılar + **localhost güvenlik kontrolü** |
| `betikler/kontrol.py` | Kurulum sağlık kontrolü (TAMAM/HATA) |
| `betikler/kayit_proxy.py` | MAVLink kayıt proxy'si (projenin kalbi) |
| `betikler/kanal.py` | Kanal bozulması: gecikme, titreşim, kayıp, zamanlı gönderim |
| `betikler/kayit_yazici.py` | Arka planda akış hâlinde Parquet yazımı, kurtarma günlüğü |
| `betikler/proxy_performans.py` | SITL'siz proxy döngü gecikmesi ölçümü |
| `betikler/ucus_yap.py` | Görev yükler, arm/AUTO/kalkış, uçurur |
| `betikler/normal_uretim.sh` | Tek komutla normal uçuş |
| `betikler/saldiri_uret.sh` | Tek komutla saldırılı uçuş |
| `betikler/toplu_uretim.py` | Gece boyu insansız toplu üretim (SITL'yi kendisi yönetir) |
| `betikler/saldirilar/*.py` | 5 saldırı + `saldiri_temel.py` (ortak argümanlar, ground_truth yazımı) |
| `betikler/etiketle.py` | `label` sütunu ekler |
| `betikler/komut_yanit.py` | Komut–yanıt tutarlılığı öznitelikleri (10 sütun) |
| `betikler/oznitelik.py` | 1 sn pencere öznitelikleri → `veri/oznitelikler/pencereler.parquet` |
| `betikler/bol.py` | Uçuş düzeyinde katmanlı bölme → `veri/bolme.csv` |
| `betikler/dogrula.py` | Uçuş klasörü eksiksizlik kontrolü |
| `gorevler/*.waypoints` | 5 görev dosyası |
| `belgeler/` | Türkçe rehberler (aşağıda) |

**Belgeler:** `KURULUM.md` → `VERI_URETIMI.md` → `VERI_PAYLASIMI.md` (sıralı);
`VERI_SEMASI.md`, `SORUN_GIDERME.md` ve `UCUS_NUMARALARI.md` başvuru belgeleri;
`MIMARI.md` sistemin bütünü; `YOL_HARITASI.md` görev takibinin tek doğru kaynağı;
`G7_RAPOR.md` uçtan uca doğrulama raporu.
Bir konuda çalışmadan önce
ilgili belgeyi oku; kodu değiştirirsen belgeyi de güncelle.

## 6. Sık kullanılan komutlar

```bash
bash setup.sh                         # kurulum (15-30 dk, ArduPlane derler)
source .venv/bin/activate
python betikler/kontrol.py            # hepsi TAMAM olmalı

# Ayrı terminalde SITL:
cd ~/ardupilot/ArduPlane && sim_vehicle.py -v ArduPlane --no-mavproxy

# Normal uçuş: <ucus_id> <gorev> [sure] ...
bash betikler/normal_uretim.sh F101_normal gorevler/gorev1_dikdortgen.waypoints 180 3 90
# Saldırılı uçuş: <ucus_id> <gorev> <saldiri> [sure] [saldiri_sure] [gecikme] [ekstra...]
bash betikler/saldiri_uret.sh F106_spoof_cmd gorevler/gorev1_dikdortgen.waypoints spoof_cmd 180 30 60

# İşleme hattı
python betikler/etiketle.py --hepsi
python betikler/oznitelik.py --hepsi
python betikler/bol.py
python betikler/dogrula.py --hepsi
```

Testler `tests/` altında pytest ile yazılır ve `pytest tests/` ile çalışır.
**Her görev SITL gerektirmeyen testler ekler.** Gerçek uçuş davranışı ayrıca
`kontrol.py`, `dogrula.py` ve gerçek SITL çalıştırmasıyla doğrulanır. Statik
kontrol için: `python -m py_compile betikler/*.py betikler/saldirilar/*.py` ve
`bash -n betikler/*.sh`.

## 7. Ekip ve makineler

Ekip 4 kişi, 5 makinedir; uçuş numaraları çakışmasın diye her makinenin kendi `pc_id`'si vardır:

| pc_id | Uçuş aralığı | Makine |
|-------|--------------|--------|
| pc1 | F100–F199 | Batuhan masaüstü — Pop!_OS 24.04 (noble tabanlı) |
| pc2 | F200–F299 | Şeyma laptop — Ubuntu 26.04 |
| pc3 | F300–F399 | Hasan laptop — Ubuntu 26.04 |
| pc4 | F400–F499 | Yusuf laptop — Ubuntu 26.04 |
| pc5 | F500–F599 | Batuhan laptop |

Şeyma, Hasan ve Yusuf'un laptopları Ubuntu **26.04**'tür. `setup.sh` 22.04 ve sonrasındaki her
Ubuntu'da devam eder, ama 26.04'te Plane-4.7.2 derlemesi henüz denenmedi
(README'deki "Ubuntu 26.04 hakkında" notu). 26.04'te kurulum/derleme hatası
çıkarsa çözümü `belgeler/SORUN_GIDERME.md`'ye ve README notuna işle.

Uçuş adı biçimi: `F<numara>_<tür>` (tür: `normal` veya saldırı adı).
**Numara ekip genelinde tektir** (tür farklı olsa bile). Kurallar ve tam cihaz
tablosu: `belgeler/UCUS_NUMARALARI.md` (tek doğru kaynak; tablo değişirse orayı
ve README'yi güncelle).

- Bir oturumun başında `config.yaml`'daki `pc_id` ve `ucus_no_araligi`'nın
  kullanıcının o anki cihazıyla uyuştuğunu kullanıcıya sorarak doğrula.
  Batuhan'ın iki makinesi ayrı `pc_id` kullanır: masaüstü `pc1`, laptop `pc5`.
- Uçuş komutu önerirken numarayı uydurma: `python betikler/ortak.py --sonraki <tür>`
  ile sıradaki boş adı al.
- Çakışma koruması `ortak.py` içindedir (`config_aralik_dogrula`,
  `ucus_id_dogrula`); `kayit_proxy.py`, `ucus_yap.py`, `normal_uretim.sh`,
  `saldiri_uret.sh` bunu çağırır. Bu kontrolleri gevşetme/atlatma; "zaten
  kullanılmış" hatasında kullanıcıya sormadan klasör silme.

## 8. Güncel durum

Projenin güncel durumu ve yapılacak işler için **tek doğru kaynak
`belgeler/YOL_HARITASI.md`'dir**. Durumu buraya yazma, orayı güncelle.

**Bir göreve başlamadan önce `belgeler/MIMARI.md` ve `belgeler/YOL_HARITASI.md`'yi
oku.**

**"Sıradaki görev" kuralı:** Kullanıcı "sıradaki görev" dediğinde
`YOL_HARITASI.md`'deki ilk işaretlenmemiş görevi yap. Bitince: tüm testleri
çalıştır, kabul ölçütünü kontrol et, kutucuğu `[x]` yap, tarihi ve kısa bir not
yaz, Türkçe commit at, sonra dur ve kullanıcıya özet ver. Kabul ölçütü
sağlanmazsa kutucuğu işaretleme, nedenini yaz.

## 9. Git

- Ana dal `main`. Commit mesajları Türkçe, kısa ve emir kipinde
  (ör. "Kurulumu Pop!_OS için uyumlu hale getir").
- Yol haritası işleri `veri-duzeltmeleri` branch'ine commit'lenir.
- Kullanıcı istemeden commit/push yapma. Tek istisna: "sıradaki görev" o görevin
  commit'ine izin verir, **push'a değil**. Ham veri dosyalarını asla ekleme
  (`git status`'ta `.parquet`/`.tlog`/`.BIN` görürsen dur ve uyar).
