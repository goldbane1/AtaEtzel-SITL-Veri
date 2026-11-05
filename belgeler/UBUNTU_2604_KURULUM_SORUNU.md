# Ubuntu 26.04 LTS (`resolute`) / Python 3.14 Kurulum Uyumsuzluğu ve Çözüm Raporu

> **Amaç:** Bu belge, `pc2` makinesinde (**Ubuntu 26.04.1 LTS — `resolute`**, **Python 3.14.4**) kurulum öncesi yapılan detaylı statik ve ortam analizinde tespit edilen kurulum kırılmasını ve uygulanan geriye dönük uyumlu çözümü ana geliştirici / kodlama asistanı için belgelendirir.

---

## 1. Ortam Özeti (`pc2`)

| Bileşen | Değer |
|---------|-------|
| **İşletim Sistemi** | Ubuntu 26.04.1 LTS (Resolute Raccoon) |
| **Dağıtım Kod Adı (`VERSION_CODENAME`)** | `resolute` |
| **Sistem Python Sürümü** | Python 3.14.4 |
| **ArduPilot Etiketi (Sabit)** | `Plane-4.7.2` |

---

## 2. Tespit Edilen Sorunlar (Kök Neden Analizi)

Proje kuralları gereği ArduPilot sürümü **`Plane-4.7.2`** olarak sabittir. Ancak `Plane-4.7.2` etiketlendiği tarihte Ubuntu 26.04 (`resolute`) henüz yayımlanmadığı için `~/ardupilot/Tools/environment_install/install-prereqs-ubuntu.sh` betiği en son Ubuntu 25.10 (`questing`) sürümünü tanımaktadır.

`setup.sh` mevcut haliyle Ubuntu 26.04 (`resolute`) üzerinde çalıştırıldığında **üç aşamalı zincirleme hata** meydana gelmektedir:

### Sorun A — `install-prereqs-ubuntu.sh` İçinde `python-argparse` Paketi Hatası
`install-prereqs-ubuntu.sh` betiği `RELEASE_CODENAME=resolute` değerini `if/elif` listesinde bulamadığında eski dağıtımlar için yazılmış `else` dalına düşer (satır 325–336):

```bash
elif [ ${RELEASE_CODENAME} != 'mantic' ] &&
     [ ${RELEASE_CODENAME} != 'noble' ] &&
     [ ${RELEASE_CODENAME} != 'oracular' ] &&
     [ ${RELEASE_CODENAME} != 'plucky' ] &&
     [ ${RELEASE_CODENAME} != 'questing' ] &&
     true; then
    if apt-cache search python-argparse | grep argp; then
        SITL_PKGS+=" python-argparse"
```

Ubuntu 26.04'te `apt-cache search python-argparse` komutu `python3-argparse-addons` paketini döndürdüğü için `grep argp` koşulu doğru (`0`) döner ve betik **`python-argparse`** paketini `SITL_PKGS` listesine ekler. Ancak Ubuntu 26.04 depolarında `python-argparse` adında bir paket yoktur (`N: python-argparse paketi bulunamadı`).

Betik başında `set -e` bulunduğu için 419. satırdaki toplu `sudo apt-get install` komutu **hiçbir paketi kurmadan anında hata verip çıkar**.

### Sorun B — `setup.sh` İçinde `.venv` Kurulumunun Derlemeden (`./waf plane`) Sonra Olması
`setup.sh` dosyasında adımlar şu sırayla çalışmaktadır:
- **Adım 3/6:** `install-prereqs-ubuntu.sh` (hata verse bile `|| echo "[UYARI]..."` ile geçilir)
- **Adım 4/6:** `./waf configure --board sitl && ./waf plane`
- **Adım 5/6:** Repo sanal ortamı (`.venv`) oluşturulması ve `requirements.txt` kurulumu

`install-prereqs-ubuntu.sh` Sorun A yüzünden yarıda kesildiğinde:
1. ArduPilot'un kendi sanal ortamı (`~/venv-ardupilot`) hiç oluşturulmaz ve PEP 668 (`externally-managed-environment`) nedeniyle sistem Python'una paket kurulamaz.
2. **Adım 4/6** (`./waf plane`) başladığında henüz repo `.venv` ortamı da oluşturulmadığı için derleme sistem Python'u ile çalışır.
3. Derleme sırasında DroneCAN başlık üreteci (`modules/DroneCAN/dronecan_dsdlc/dronecan_dsdlc.py`, satır 12) `import em` (`empy==3.3.4`) çağrısında `ModuleNotFoundError: No module named 'em'` hatası vererek **derlemeyi durdurur (`set -e`)**.

### Sorun C — `sim_vehicle.py` PATH ve `pexpect` Eksikliği
`install-prereqs-ubuntu.sh` 419. satırda kırıldığı için 597. satırdaki `export PATH="$HOME/ardupilot/Tools/autotest:$PATH"` satırına hiç ulaşamaz. Bunun sonucunda:
1. `sim_vehicle.py` komutu `PATH` içine eklenmez (`sim_vehicle.py: command not found`).
2. `sim_vehicle.py`'nin kullandığı `Tools/autotest/pysim/util.py` (satır 19) içindeki `import pexpect` bağımlılığı ne sistemde ne de `requirements.txt` içinde yer aldığı için `sim_vehicle.py` başlatılamaz.

---

## 3. Uygulanan Çözüm (Tüm Makinelerle Geriye Dönük Uyumlu)

ArduPlane sürümü (`Plane-4.7.2`) ve veri üretim mimarisi **hiç değiştirilmeden**, Ubuntu 22.04 (`jammy`), Pop!_OS, Ubuntu 24.04 (`noble`) ve Ubuntu 26.04 (`resolute`) makinelerinin tamamında sorunsuz çalışacak şekilde iki dosyada güncelleme yapılmıştır:

### 1. `requirements.txt` Güncellemesi
Repo sanal ortamına (`.venv`) ArduPlane SITL derlemesi (`waf` / `dronecan_dsdlc.py`) ve `sim_vehicle.py` için zorunlu olan iki paket eklendi:
- `empy==3.3.4` (DroneCAN DSDL derleyicisi için zorunlu sürüm)
- `pexpect` (`sim_vehicle.py` / `pysim` için zorunlu)

### 2. `setup.sh` Güncellemesi
1. **Temel `apt` paketlerinin güçlendirilmesi (Adım 1/6):**
   `install-prereqs-ubuntu.sh` yeni bir Ubuntu sürümünde yarıda kalsa bile SITL derlemesi ve `sim_vehicle.py` için gereken `gawk`, `libtool-bin`, `libxml2-dev`, `libxslt1-dev`, `python3-pexpect` paketleri doğrudan 1. adımdaki `apt-get install` listesine eklendi.
2. **`.venv` kurulumunun derleme öncesine alınması (Adım 3/6):**
   Repo `.venv` sanal ortamının oluşturulması ve `requirements.txt` paketlerinin (`empy==3.3.4`, `pexpect`, `pymavlink`, `mavproxy` vb.) kurulumu `./waf configure --board sitl && ./waf plane` adımından **önceye** alındı.
3. **`install-prereqs-ubuntu.sh` sonrası `.venv`'nin yeniden etkinleştirilmesi ve PATH garantisi (Adım 4/6 & 5/6):**
   - `install-prereqs-ubuntu.sh` çalıştıktan sonra `~/.profile` yüklense bile derleme öncesinde `source "$REPO_KOK/.venv/bin/activate"` tekrar çağrılarak `./waf configure --board sitl && ./waf plane` komutlarının her zaman `.venv` içindeki eksiksiz Python ortamıyla derlenmesi garanti altına alındı.
   - `~/ardupilot/Tools/autotest` dizini `~/.profile` ve `~/.bashrc` içinde yoksa `setup.sh` tarafından otomatik olarak eklendi.

---

## 4. Ana Repo İçin Birleştirme Notu

Bu dal (`fix/ubuntu-2604-kurulum`) yalnızca aşağıdakileri değiştirir:
- `requirements.txt`
- `setup.sh`
- `belgeler/UBUNTU_2604_KURULUM_SORUNU.md`

> **Not:** `config.yaml` üzerindeki yerel cihaz ayarları (`pc2`, `[200, 299]`) `git update-index --skip-worktree config.yaml` ile korunduğu için bu dalda yer almaz; doğrudan `main` dalına merge edilebilir.
