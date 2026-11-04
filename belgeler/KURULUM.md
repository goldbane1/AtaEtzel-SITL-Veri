# Kurulum (KURULUM.md)

> 🧭 **Aşama 1–2 / 5** · [Yol haritası](../README.md#yol-haritası--neyi-hangi-sırayla) · Sonraki aşama → [VERI_URETIMI.md](VERI_URETIMI.md)

Bu rehber `setup.sh`'ın ne yaptığını adım adım açıklar. Kurulumu **bir kişi tek
makinede** baştan sona yapsın; repo çalışır hale gelince diğerleri yalnızca
klonlayıp `setup.sh` çalıştırır.

## Gereksinimler

- Standart desteği süren bir Ubuntu: **22.04**, **24.04** veya **26.04**
  (WSL2 dahil) ya da bunlara dayanan **Pop!_OS**. Ubuntu **20.04 ve öncesi
  desteklenmez** (ArduPilot'un kuralı).
- İnternet erişimi (ArduPilot ve pip paketleri için)
- ~5 GB boş disk, derleme için birkaç GB RAM

## Tek komut

```bash
bash setup.sh
```

## `setup.sh` ne yapıyor?

0. **Ortam kontrolü:** Dağıtımın Ubuntu tabanlı olup olmadığına (`ID` veya
   `ID_LIKE` içinde `ubuntu`) ve Ubuntu taban sürümüne bakar. Yalnızca 20.04
   ve öncesi gibi desteği bitmiş bir sürümde Türkçe uyarı verip durur; diğer
   her durumda devam eder.
1. **apt bağımlılıkları:** `git`, `python3`, `python3-venv`, `python3-dev`,
   `build-essential`, `ccache`, `rsync`.
2. **ArduPilot (Plane-4.7.2):** `~/ardupilot`'a `--branch Plane-4.7.2` ile klonlar.
   Zaten varsa klonlamayı atlar, etikete geçer ve submodule'leri günceller.
3. **Ön gereksinimler:** ArduPilot'un `Tools/environment_install/
   install-prereqs-ubuntu.sh -y` betiğini çalıştırır — MAVProxy ve pymavlink'i
   sistem geneline bu kurar. Bu betik hata verirse (ör. çok yeni bir Ubuntu
   kod adını henüz tanımıyorsa) kurulum **durmaz**: `setup.sh` Türkçe uyarı
   verir ve temel paketleri (`python3-venv`, `build-essential`, `ccache`,
   `python3-wxgtk4.0`, `python3-dev`, `libtool`, `pkg-config`) yedek adım
   olarak tek tek kurmayı dener. O sürümde bulunmayan paket atlanır.
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

## Desteklenen işletim sistemleri

> **Ubuntu 22.04 / 24.04 / 26.04 ve Pop!_OS desteklenir.** İşletim sistemini
> yükselttikten sonra (ör. 24.04 → 26.04) ArduPilot ön gereksinim adımı
> yeniden çalıştırılmalıdır:
>
> ```bash
> cd ~/ardupilot && Tools/environment_install/install-prereqs-ubuntu.sh -y
> ```
>
> ArduPlane sürümü (Plane-4.7.2) tüm makinelerde aynı olduğu sürece,
> makinelerin farklı Ubuntu tabanında olması üretilen veriyi etkilemez.

- **Kural:** `setup.sh` belirli sürümlerle sınırlı değildir. ArduPilot'un
  kuralını izler: *standart desteği süren her Ubuntu* desteklenir, 20.04 ve
  öncesi desteklenmez. Hangi Ubuntu'nun gerçekten desteklendiğine ArduPilot'un
  kendi `install-prereqs-ubuntu.sh` betiği karar verir.
- **Yeni çıkmış bir sürüm** (ör. 26.04'ten sonraki) kullanıyorsanız `setup.sh`
  yine devam eder. ArduPilot betiği kod adını tanımazsa yedek adım devreye
  girer (yukarıda 3. madde); derleme hata verirse çıktıyı not alıp
  [SORUN_GIDERME.md](SORUN_GIDERME.md)'ye bakın.
- 24.04 ve sonrasında bazı Python paketleri "externally managed" uyarısı
  verebilir; repo bağımlılıkları **.venv** içine kurulduğu için bu bizi
  etkilemez.
- ArduPlane 4.7 ile bazı parametreler `SRn_*` yerine `MAVn_*` adıyla geçer; bu
  normaldir.

## Pop!_OS kullanıyorsanız

- Pop!_OS, Ubuntu tabanlıdır (`/etc/os-release` içinde `ID=pop` ve
  `ID_LIKE="ubuntu debian"`). `setup.sh`, `ID` `ubuntu` olmasa bile `ID_LIKE`
  içinde `ubuntu` geçtiği için dağıtımı Ubuntu türevi olarak kabul eder ve
  devam eder; ek bir işlem gerekmez.
- Ubuntu taban sürümü `UBUNTU_CODENAME` alanından okunur (Pop!_OS 22.04 →
  `jammy`, 24.04 → `noble`). Linux Mint gibi kendi sürüm numarasını kullanan
  türevlerde de bu sayede doğru Ubuntu tabanı bulunur.

## Makinelerin sürümü aynı değilse

- Ekipte 22.04, 24.04, 26.04 ve Pop!_OS karışık olabilir. ArduPlane **kaynaktan
  Plane-4.7.2'de** derlendiği için işletim sistemi sürüm farkı sonuçları
  etkilemez — önemli olan tüm makinelerde **aynı ArduPlane etiketi**dir.

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
