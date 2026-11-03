# Sorun Giderme (SORUN_GIDERME.md)

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
  `ucus_yap.py` arm + AUTO + `MISSION_START` gönderir; SITL konsolunda
  "ARMED" ve "Mission" mesajlarını izleyin. Rüzgâr çok yüksekse düşürün.

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

## `ground_truth.json` oluşmuyor
- **Neden:** Saldırı betiği hiç çalışmadı veya `--ucus` adı proxy'nin uçuşuyla
  aynı değil.
- **Çözüm:** Saldırı betiğindeki `--ucus` ile proxy'nin `--ucus`'u **birebir aynı**
  olmalı.
