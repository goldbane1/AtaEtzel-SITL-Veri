# Kurulum (KURULUM.md)

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

## Ubuntu 22.04 ve 24.04 farkları

- Her iki sürümde de `install-prereqs-ubuntu.sh` çalışır. 24.04'te bazı Python
  paketleri "externally managed" uyarısı verebilir; repo bağımlılıkları **.venv**
  içine kurulduğu için bu bizi etkilemez.
- ArduPlane 4.7 ile bazı parametreler `SRn_*` yerine `MAVn_*` adıyla geçer; bu
  normaldir.

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
