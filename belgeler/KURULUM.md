# Kurulum (KURULUM.md)

> 🧭 **Aşama 1–2 / 5** · [Yol haritası](../README.md#yol-haritası--neyi-hangi-sırayla) · Sonraki aşama → [VERI_URETIMI.md](VERI_URETIMI.md)

Bu rehber `setup.sh`'ın ne yaptığını adım adım açıklar. Kurulumu **bir kişi tek
makinede** baştan sona yapsın; repo çalışır hale gelince diğerleri yalnızca
klonlayıp `setup.sh` çalıştırır.

## Gereksinimler

- Ubuntu **22.04** veya **24.04** (WSL2 dahil)
- İnternet erişimi (ArduPilot ve pip paketleri için)
- ~5 GB boş disk, derleme için birkaç GB RAM

## Tek komut

```bash
bash setup.sh
```

## `setup.sh` ne yapıyor?

1. **apt bağımlılıkları:** `git`, `python3`, `python3-venv`, `python3-dev`,
   `build-essential`, `ccache`, `rsync`.
2. **ArduPilot (Plane-4.7.2):** `~/ardupilot`'a `--branch Plane-4.7.2` ile klonlar.
   Zaten varsa klonlamayı atlar, etikete geçer ve submodule'leri günceller.
3. **Ön gereksinimler:** ArduPilot'un `Tools/environment_install/
   install-prereqs-ubuntu.sh -y` betiğini çalıştırır — MAVProxy ve pymavlink'i
   sistem geneline bu kurar.
4. **Derleme:** `./waf configure --board sitl && ./waf plane` (15–30 dk).
5. **Repo sanal ortamı:** `.venv` oluşturur ve `requirements.txt`'i kurar.
6. **Özet:** Yolları ve sonraki adımı (sağlık kontrolü) yazar.

Bir adım başarısız olursa betik `set -e` ile durur ve son hatayı gösterir.

## Kurulumdan sonra

```bash
source .venv/bin/activate
python betikler/kontrol.py
```

Tüm satırlar **TAMAM** olmalı. HATA varsa çıktıyı not alıp
[SORUN_GIDERME.md](SORUN_GIDERME.md)'ye bakın.

## Cihazınızın uçuş numarası aralığını ayarlayın (zorunlu)

`config.yaml`'da `pc_id` ve `ucus_no_araligi`'nı kendi cihazınıza göre ayarlayın
(ör. 2. kişi: `pc_id: pc2`, `ucus_no_araligi: [200, 299]`), sonra
`python betikler/kontrol.py`'yi tekrar çalıştırın. Kimin hangi aralığı
kullandığı, neden önemli olduğu ve ayarın git'e gitmemesi için yapılacaklar:
[UCUS_NUMARALARI.md](UCUS_NUMARALARI.md) (5. bölüm).

## Ubuntu 22.04 ve 24.04 farkları

- Her iki sürümde de `install-prereqs-ubuntu.sh` çalışır. 24.04'te bazı Python
  paketleri "externally managed" uyarısı verebilir; repo bağımlılıkları **.venv**
  içine kurulduğu için bu bizi etkilemez.
- ArduPlane 4.7 ile bazı parametreler `SRn_*` yerine `MAVn_*` adıyla geçer; bu
  normaldir.

## Pop!_OS 22.04 / 24.04 kullanıyorsanız

- Pop!_OS, Ubuntu tabanlıdır (`/etc/os-release` içinde `ID=pop` ve
  `ID_LIKE=ubuntu`). `setup.sh`, `ID` `ubuntu` olmasa bile `ID_LIKE` içinde
  `ubuntu` geçtiği için dağıtımı Ubuntu türevi olarak kabul eder ve devam eder;
  ek bir işlem gerekmez.
- Pop!_OS 22.04/24.04 kullananlarda `lsb_release -cs` **`jammy`** veya
  **`noble`** dönebilir; ikisi de desteklenir. ArduPlane sürümü (Plane-4.7.2)
  tüm makinelerde aynı olduğu sürece işletim sistemi tabanının farklı olması
  sorun değildir.
- `setup.sh` kod adı kontrolünü sert bir engel yapmaz: `jammy`/`noble`'da
  sorunsuz devam eder, başka bir kod adında yalnızca Türkçe bir uyarı verip yine
  de dener. Nihai kararı ArduPilot'un `install-prereqs-ubuntu.sh` betiği verir.

## Üç makinenin sürümü aynı değilse

- Ekipte 22.04 (Pop!_OS dahil) ve 24.04 karışık olabilir. ArduPlane **kaynaktan
  Plane-4.7.2'de** derlendiği için işletim sistemi sürüm farkı sonuçları
  etkilemez — önemli olan üç makinede de **aynı ArduPlane etiketi**dir.

## WSL kullanıyorsanız

- Kurulum ve komut satırı sorunsuz çalışır.
- Harita/konsol penceresi (GUI) açılmayabilir. Bu bir sorun değildir: SITL'yi
  `--map` olmadan çalıştırın; veri üretimi GUI gerektirmez.
- SITL'yi başlatırken `--no-mavproxy` kullanın (biz kendi proxy'mizi kullanıyoruz).

## Sık hatalar

- **`sim_vehicle.py: command not found`** → `source ~/.profile` çalıştırın ya da
  terminali yeniden açın; `install-prereqs` PATH'e ekler.
- **`./waf` derleme hatası** → `git submodule update --init --recursive` çalıştırıp
  tekrar deneyin.
- Daha fazlası: [SORUN_GIDERME.md](SORUN_GIDERME.md).
