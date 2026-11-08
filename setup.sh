#!/usr/bin/env bash
# =====================================================================
# setup.sh — AtaEtzel SITL veri üretimi için baştan sona kurulum.
# ---------------------------------------------------------------------
# Standart desteği süren her Ubuntu'da (22.04, 24.04, 26.04 ...) ve
# Ubuntu tabanlı dağıtımlarda (Pop!_OS vb.) çalışır. Hangi Ubuntu'nun
# desteklendiğine ArduPilot'un install-prereqs-ubuntu.sh betiği karar
# verir; bu betik yalnızca desteği bitmiş (20.04 ve öncesi) sürümlerde durur.
# Yaptıkları:
#   0) Dağıtım/sürüm kontrolü
#   1) apt bağımlılıkları (git, python3, venv, build-essential vb.)
#   2) ArduPilot'u Plane-4.7.2 etiketinde ~/ardupilot'a klonlar (varsa atlar)
#   3) Bu repo için .venv oluşturup requirements.txt'i kurar (waf için empy/pexpect dahil)
#   4) ArduPilot'un install-prereqs-ubuntu.sh betiğini çalıştırır ve PATH'i ayarlar.
#      Başarısız olursa temel apt paketlerini yedek adım olarak ayrıca kurmayı dener.
#   5) ./waf configure --board sitl && ./waf plane ile ArduPlane'i derler
#   6) Özet basar
#
# Her adımda Türkçe ilerleme mesajı verir; bir adım başarısız olursa
# (set -e) açık bir hata ile durur.
#
# Kullanım:  bash setup.sh
# =====================================================================
set -euo pipefail

ARDUPILOT_DIZIN="${HOME}/ardupilot"
ARDUPILOT_ETIKET="Plane-4.7.2"
REPO_KOK="$(cd "$(dirname "$0")" && pwd)"

bilgi()  { echo -e "\n[BILGI] $*"; }
tamam()  { echo "[TAMAM] $*"; }
hata()   { echo "[HATA] $*" >&2; }

trap 'hata "Kurulum bir adımda durdu. Yukarıdaki son hatayı inceleyin."' ERR

bilgi "0/6 Ortam kontrol ediliyor..."
# /etc/os-release'ten dağıtım bilgisini oku (ID, ID_LIKE, VERSION_ID,
# VERSION_CODENAME ve Ubuntu türevlerinde UBUNTU_CODENAME gelir).
. /etc/os-release 2>/dev/null || true
echo "       Dağıtım: ${PRETTY_NAME:-bilinmiyor}"

# 0a) Ubuntu tabanlı mı? Pop!_OS'ta ID=pop, ID_LIKE="ubuntu debian" olur;
#     bu yüzden hem ID'ye hem ID_LIKE'a bakılır.
if [[ "${ID:-}" == "ubuntu" || " ${ID_LIKE:-} " == *" ubuntu "* ]]; then
  echo "       Ubuntu tabanlı bir dağıtım algılandı (ID=${ID:-?}, ID_LIKE=${ID_LIKE:-yok})."
else
  echo "[UYARI] Ubuntu tabanlı bir dağıtım algılanamadı (ID=${ID:-?}, ID_LIKE=${ID_LIKE:-yok})."
  echo "        Yine de devam ediliyor; nihai kararı ArduPilot'un install-prereqs betiği verecek."
fi

# 0b) Hangi Ubuntu TABANI? Türevlerde (Pop!_OS, Mint...) dağıtımın kendi
#     sürüm numarası Ubuntu'nunkinden farklı olabilir; bu yüzden önce
#     UBUNTU_CODENAME'e bakılır.
KOD_ADI="${UBUNTU_CODENAME:-${VERSION_CODENAME:-$(lsb_release -cs 2>/dev/null || true)}}"
echo "       Ubuntu kod adı: ${KOD_ADI:-bilinmiyor}"

# Kod adı -> Ubuntu sürümü. Bu liste bir ENGEL LİSTESİ DEĞİLDİR; yalnızca
# sürümün eski mi yeni mi olduğunu anlamak içindir. Listede olmayan (daha
# yeni) kod adları otomatik olarak "yeni" sayılır ve kurulum devam eder.
case "${KOD_ADI:-}" in
  trusty)   UBUNTU_SURUM="14.04" ;;
  xenial)   UBUNTU_SURUM="16.04" ;;
  bionic)   UBUNTU_SURUM="18.04" ;;
  focal)    UBUNTU_SURUM="20.04" ;;
  jammy)    UBUNTU_SURUM="22.04" ;;
  kinetic)  UBUNTU_SURUM="22.10" ;;
  lunar)    UBUNTU_SURUM="23.04" ;;
  mantic)   UBUNTU_SURUM="23.10" ;;
  noble)    UBUNTU_SURUM="24.04" ;;
  oracular) UBUNTU_SURUM="24.10" ;;
  plucky)   UBUNTU_SURUM="25.04" ;;
  questing) UBUNTU_SURUM="25.10" ;;
  resolute) UBUNTU_SURUM="26.04" ;;
  *)
    # Bilinmeyen kod adı: saf Ubuntu'daysak VERSION_ID doğrudan Ubuntu sürümüdür.
    if [[ "${ID:-}" == "ubuntu" ]]; then UBUNTU_SURUM="${VERSION_ID:-}"; else UBUNTU_SURUM=""; fi ;;
esac

# 0c) ArduPilot kuralı: standart desteği süren her Ubuntu desteklenir;
#     20.04 ve öncesi desteklenmez. Yalnızca bu durumda dur.
if [[ "$UBUNTU_SURUM" =~ ^([0-9]+)\.([0-9]+) ]]; then
  SURUM_SAYI=$(( 10#${BASH_REMATCH[1]} * 100 + 10#${BASH_REMATCH[2]} ))
  if (( SURUM_SAYI < 2204 )); then
    hata "Ubuntu tabanı ${UBUNTU_SURUM} (${KOD_ADI:-?}) çok eski; standart desteği bitmiş."
    hata "ArduPilot 20.04 ve öncesini desteklemez. Lütfen Ubuntu 22.04, 24.04 veya"
    hata "26.04'e (ya da bunlara dayanan Pop!_OS sürümüne) yükseltip tekrar deneyin."
    trap - ERR
    exit 1
  fi
  echo "       Ubuntu tabanı ${UBUNTU_SURUM}; desteklenen aralıkta (22.04 ve sonrası), devam ediliyor."
else
  echo "[UYARI] Ubuntu taban sürümü tespit edilemedi (kod adı: ${KOD_ADI:-yok})."
  echo "        Daha yeni bir sürüm olduğu varsayılarak devam ediliyor; desteklenip"
  echo "        desteklenmediğine ArduPilot'un install-prereqs-ubuntu.sh betiği karar verecek."
fi

bilgi "1/6 apt bağımlılıkları kuruluyor (sudo gerekebilir)..."
sudo apt-get update
sudo apt-get install -y \
  git python3 python3-pip python3-venv python3-dev \
  build-essential ccache rsync gawk libtool-bin \
  libxml2-dev libxslt1-dev python3-pexpect
tamam "apt bağımlılıkları kuruldu."

bilgi "2/6 ArduPilot (${ARDUPILOT_ETIKET}) hazırlanıyor..."
if [[ -d "$ARDUPILOT_DIZIN/.git" ]]; then
  echo "       ArduPilot zaten mevcut: $ARDUPILOT_DIZIN (klonlama atlanıyor)."
  cd "$ARDUPILOT_DIZIN"
  git fetch --tags --depth 1 origin "$ARDUPILOT_ETIKET" || git fetch --tags
  git checkout "$ARDUPILOT_ETIKET"
else
  git clone --recurse-submodules --branch "$ARDUPILOT_ETIKET" --depth 1 \
    https://github.com/ArduPilot/ardupilot.git "$ARDUPILOT_DIZIN"
  cd "$ARDUPILOT_DIZIN"
fi
echo "       Submodule'ler güncelleniyor..."
git submodule update --init --recursive
tamam "ArduPilot ${ARDUPILOT_ETIKET} hazır."

bilgi "3/6 Repo sanal ortamı (.venv) oluşturuluyor (derleme ve betik bağımlılıkları)..."
cd "$REPO_KOK"
if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source "$REPO_KOK/.venv/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt
tamam "Sanal ortam ve Python bağımlılıkları kuruldu."

bilgi "4/6 ArduPilot ön gereksinimleri ve PATH ayarlanıyor..."
cd "$ARDUPILOT_DIZIN"
# Desteklenen Ubuntu kararını ArduPilot'un kendi betiği verir. Betik kod adını
# tanımazsa (ör. Ubuntu 26.04 resolute) hata verebilir; bu durumda kurulum DURMAZ.
# Derleme için gereken empy/pexpect/pymavlink zaten 3. adımda .venv içine kuruldu.
ON_GEREKSINIM_TAMAM=0
if [[ -f "Tools/environment_install/install-prereqs-ubuntu.sh" ]]; then
  if USER="${USER:-$(whoami)}" Tools/environment_install/install-prereqs-ubuntu.sh -y; then
    ON_GEREKSINIM_TAMAM=1
  else
    echo "[UYARI] install-prereqs-ubuntu.sh hata verdi (kod adını tanımamış olabilir:"
    echo "        '${KOD_ADI:-bilinmiyor}'). Kurulum durdurulmuyor; yedek adıma geçiliyor."
  fi
else
  echo "[UYARI] install-prereqs-ubuntu.sh bulunamadı; yedek adıma geçiliyor."
fi

if [[ "$ON_GEREKSINIM_TAMAM" -ne 1 ]]; then
  echo "[UYARI] YEDEK ADIM: eksik olabilecek temel apt paketleri tek tek kuruluyor."
  echo "        (Bir paket bu sürümde yoksa atlanır; MAVProxy/pymavlink 3. adımda .venv'e kuruldu.)"
  YEDEK_PAKETLER=(python3-venv build-essential ccache python3-wxgtk4.0 python3-dev libtool pkg-config)
  KURULAMAYAN=()
  for paket in "${YEDEK_PAKETLER[@]}"; do
    if sudo apt-get install -y "$paket"; then
      echo "       + $paket kuruldu."
    else
      echo "[UYARI] $paket kurulamadı (bu sürümde adı farklı ya da yok olabilir); atlanıyor."
      KURULAMAYAN+=("$paket")
    fi
  done
  if (( ${#KURULAMAYAN[@]} > 0 )); then
    echo "[UYARI] Kurulamayan paketler: ${KURULAMAYAN[*]}"
    echo "        python3-wxgtk4.0 yalnızca harita/konsol penceresi içindir; veri üretimi için şart değildir."
  fi
  echo "[UYARI] ArduPilot ön gereksinim betiği tam çalışmadı. Derleme (5. adım) hata verirse"
  echo "        betiğin çıktısını inceleyin ve belgeler/KURULUM.md'deki notlara bakın."
fi
# sim_vehicle.py (Tools/autotest) PATH içinde yoksa ~/.profile ve ~/.bashrc'ye ekle
AUTOTEST_YOL="$ARDUPILOT_DIZIN/Tools/autotest"
EXPORT_SATIR="export PATH=\"$AUTOTEST_YOL:\$PATH\""
for PROFIL_DOSYA in "${HOME}/.profile" "${HOME}/.bashrc"; do
  if [[ -f "$PROFIL_DOSYA" ]] && ! grep -Fq "$AUTOTEST_YOL" "$PROFIL_DOSYA" 2>/dev/null; then
    echo "$EXPORT_SATIR" >> "$PROFIL_DOSYA"
  fi
done
export PATH="$AUTOTEST_YOL:$PATH"
# install-prereqs başka bir sanal ortam etkinleştirmiş olabileceği için repo .venv'sini tekrar etkinleştir
# shellcheck disable=SC1091
source "$REPO_KOK/.venv/bin/activate"
tamam "Ön gereksinimler ve PATH adımı tamamlandı."

bilgi "5/6 ArduPlane SITL derleniyor (15-30 dk sürebilir)..."
cd "$ARDUPILOT_DIZIN"
./waf configure --board sitl
./waf plane
tamam "ArduPlane SITL derlendi."

bilgi "6/6 Kurulum özeti"
cat <<OZET

========================================================================
  KURULUM TAMAM
------------------------------------------------------------------------
  ArduPilot : $ARDUPILOT_DIZIN  (etiket: $ARDUPILOT_ETIKET)
  Repo      : $REPO_KOK
  Sanal ort.: $REPO_KOK/.venv

  SONRAKİ ADIM — sağlık kontrolü:
    source .venv/bin/activate
    python betikler/kontrol.py

  Hepsi TAMAM ise, belgeler/VERI_URETIMI.md ile ilk uçuşı üretin.
========================================================================
OZET
tamam "setup.sh bitti."
