# Sorun Giderme (SORUN_GIDERME.md)

> 🧭 **Başvuru belgesi** (sıralı akışın parçası değil) · [Yol haritası](../README.md#yol-haritası--neyi-hangi-sırayla)

Her sorun için **belirti → neden → çözüm** verilmiştir.

## `sim_vehicle.py: command not found`
- **Neden:** `install-prereqs` PATH'i güncelledi ama terminal yüklemedi.
- **Çözüm:** `source ~/.profile` veya terminali yeniden açın. Kalıcı çözüm:
  `~/ardupilot/Tools/autotest`'i PATH'e ekleyin.

## `./waf` derleme hatası
- **Neden:** Submodule'ler eksik veya yarım.
- **Çözüm:**
  ```bash
  cd ~/ardupilot
  git submodule update --init --recursive
  ./waf distclean && ./waf configure --board sitl && ./waf plane
  ```

## Port dolu / `Address already in use`
- **Neden:** Önceki SITL veya proxy kapanmamış.
- **Çözüm:**
  ```bash
  pkill -f sim_vehicle
  pkill -f kayit_proxy
  ```
  `python betikler/kontrol.py` ile portların boş olduğunu doğrulayın.

## Proxy "SITL'ye bağlanılamadı" diyor
- **Neden:** SITL henüz 5760'ta dinlemiyor veya `--no-mavproxy` unutulmuş.
- **Çözüm:** Önce SITL'yi başlatın:
  `cd ~/ardupilot/ArduPlane && sim_vehicle.py -v ArduPlane --no-mavproxy`.
  Konsolda "Waiting for connection" gördükten sonra proxy'yi başlatın.

## Harita açılmıyor (WSL)
- **Neden:** WSL'de GUI penceresi yok.
- **Çözüm:** Sorun değil. SITL'yi `--map` olmadan çalıştırın; veri üretimi GUI
  gerektirmez. Gerekirse X sunucusu (VcXsrv) kurabilirsiniz, ama şart değil.

## Uçak AUTO'da kalkmıyor
- **Neden:** Görevde NAV_TAKEOFF yok, arm olmadı ya da `MISSION_START` gitmedi.
- **Çözüm:** Görev dosyasının ilk komutunun NAV_TAKEOFF (22) olduğundan emin olun.
  `ucus_yap.py` GPS ve ön-arm kontrollerini bekler, sonra arm + AUTO +
  `MISSION_START` gönderir ve ACK'leri denetler. Neden `meta.json`'daki
  `basarisizlik_nedeni` alanında yazar. Rüzgâr çok yüksekse düşürün.

## Uçuş başarısız sayıldı (`ucus_basarili: false`)
- **Neden:** Kalkış 120 sn içinde doğrulanamadı: irtifa 50 m'yi geçmedi ya da AUTO'da
  waypoint ilerlemedi. Betik 1 koduyla çıkar, saldırılı uçuşta saldırı hiç başlamaz.
- **Çözüm:** `kalkis_kontrolu` alanlarına bakın; o uçuşu veri setine katmayın.

## İkinci uçuş tuhaf davranıyor / uçak zaten havada
- **Neden:** SITL açık kaldı; önceki uçuşun uçağı hâlâ uçuyor.
- **Çözüm:** Her uçuştan önce SITL'yi yeniden başlatın. `sim_vehicle.py`'yi kapatmak
  yetmeyebilir, `arduplane` ayrı bir `xterm` içinde çalışmaya devam edebilir. Portun
  boşaldığını `ss -tln | grep 5760` ile doğrulayın.

## Parquet'te paket sırası mantıksız / ilk saniyelerde telemetri yok
- **Belirti:** Paketler ilk saniyelerde hiç görünmüyor, sonra aynı zaman damgasıyla
  yığılıyor; `MISSION_ITEM`, onu isteyen `MISSION_REQUEST`'ten önce görünüyor.
- **Neden:** SITL bağlantı başında MAVLink olmayan bayt yollar. Varsayılan modda
  `pymavlink` burada takılıp mesajları geciktirir. `kayit_proxy.py` artık
  `robust_parsing` kullanır; bu düzeltmeden önce üretilen uçuşlarda (`F100`, `F101`)
  ilk saniyelerin zaman damgaları güvenilir değildir.
- **Çözüm:** Eski uçuşları veri setine katmayın. Telemetrinin başladığı anı ve görev
  mesajlarının sırasını kontrol edin.

## `paketler.parquet` boş
- **Neden:** Proxy'ye hiç trafik gelmedi (GCS/uçuş proxy'ye değil doğrudan SITL'ye
  bağlandı), ya da proxy çok erken kapatıldı.
- **Çözüm:** `ucus_yap.py` ve saldırı betiklerinin **14550 (proxy)** üzerinden
  bağlandığından emin olun. Proxy'yi uçuş bitmeden kapatmayın.

## `pymavlink` / `pandas` import edilemiyor
- **Neden:** Sanal ortam etkin değil ya da kurulum yarım.
- **Çözüm:** `source .venv/bin/activate` sonra `pip install -r requirements.txt`.
  `python betikler/kontrol.py` ile doğrulayın.

## Saldırı betiği "GÜVENLİK" hatası veriyor
- **Neden:** Hedef localhost değil. **Bu beklenen ve istenen davranıştır.**
- **Çözüm:** `config.yaml`'da `host: "127.0.0.1"` olmalı. Bu kontrol betiklerin
  dış ağa çıkmasını engeller; **silmeyin**.

## "bu cihazın numara aralığında DEĞİL" / "zaten kullanılmış" / "config.yaml uyumsuz"
- **Neden:** Uçuş adı bu cihaza ait değil, daha önce kullanılmış ya da
  `config.yaml`'daki `pc_id` ile `ucus_no_araligi` birbirini tutmuyor. Bu
  kontroller veri kaybını önlemek için **bilerek** konmuştur.
- **Çözüm:** Hata mesajındaki "sıradaki boş ad"ı kullanın veya
  `python betikler/ortak.py --sonraki <tür>` çalıştırın. Ayrıntı ve tüm
  durumlar: [UCUS_NUMARALARI.md](UCUS_NUMARALARI.md).

## `ground_truth.json` oluşmuyor
- **Neden:** Saldırı betiği hiç çalışmadı veya `--ucus` adı proxy'nin uçuşuyla
  aynı değil.
- **Çözüm:** Saldırı betiğindeki `--ucus` ile proxy'nin `--ucus`'u **birebir aynı**
  olmalı.
