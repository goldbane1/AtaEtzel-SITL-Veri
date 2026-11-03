#!/usr/bin/env bash
# =====================================================================
# setup.sh — AtaEtzel SITL veri üretimi için baştan sona kurulum.
# ---------------------------------------------------------------------
# Ubuntu 22.04 ve 24.04'te çalışır. Yaptıkları:
#   1) apt bağımlılıkları (git, python3, venv, build-essential vb.)
#   2) ArduPilot'u Plane-4.7.2 etiketinde ~/ardupilot'a klonlar (varsa atlar)
#   3) ArduPilot'un install-prereqs-ubuntu.sh betiğini çalıştırır
#      (MAVProxy ve pymavlink'i sistem genelinde bu kurar)
#   4) ./waf configure --board sitl && ./waf plane ile ArduPlane'i derler
#   5) Bu repo için .venv oluşturup requirements.txt'i kurar
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
# /etc/os-release'ten dağıtım bilgisini oku (ID, ID_LIKE, VERSION_ID gelir).
. /etc/os-release 2>/dev/null || true
echo "       Dağıtım: ${PRETTY_NAME:-bilinmiyor}"

# Kod adını al (Ubuntu'da jammy=22.04, noble=24.04; Pop!_OS 24.04'te de noble döner).
KOD_ADI="$(lsb_release -cs 2>/dev/null || echo "${VERSION_CODENAME:-}")"
echo "       Kod adı: ${KOD_ADI:-bilinmiyor}"

# Pop!_OS'ta ID=pop, ID_LIKE=ubuntu olur; Ubuntu türevi mi diye ID ve ID_LIKE'a bak.
if [[ "${ID:-}" == "ubuntu" || " ${ID_LIKE:-} " == *" ubuntu "* ]]; then
  echo "       Ubuntu tabanlı bir dağıtım algılandı (ID=${ID:-?}, ID_LIKE=${ID_LIKE:-yok})."
else
  echo "[UYARI] Ubuntu tabanlı bir dağıtım algılanamadı (ID=${ID:-?}, ID_LIKE=${ID_LIKE:-yok})."
  echo "        Yine de devam ediliyor; nihai kararı ArduPilot'un install-prereqs betiği verecek."
fi

# Kod adı kontrolü SERT BİR ENGEL DEĞİL: jammy/noble sorunsuz devam eder,
# diğerlerinde yalnızca Türkçe uyarı verilir (kurulum durdurulmaz).
case "${KOD_ADI:-}" in
  jammy|noble)
    echo "       Desteklenen kod adı (${KOD_ADI}); devam ediliyor." ;;
  "")
    echo "[UYARI] Kod adı tespit edilemedi; kurulum yine de denenecek." ;;
  *)
    echo "[UYARI] '${KOD_ADI}' jammy/noble değil; test edilmedi."
    echo "        Kurulum yine de denenecek, desteklenip desteklenmediğine"
    echo "        ArduPilot'un install-prereqs-ubuntu.sh betiği karar verecek." ;;
esac

bilgi "1/6 apt bağımlılıkları kuruluyor (sudo gerekebilir)..."
sudo apt-get update
sudo apt-get install -y \
  git python3 python3-pip python3-venv python3-dev \
  build-essential ccache rsync
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

bilgi "3/6 ArduPilot ön gereksinimleri kuruluyor (MAVProxy, pymavlink)..."
# Betik PATH ve kullanıcı değişkenlerine dokunduğu için hataya izin veriyoruz.
if [[ -f "Tools/environment_install/install-prereqs-ubuntu.sh" ]]; then
  USER="${USER:-$(whoami)}" Tools/environment_install/install-prereqs-ubuntu.sh -y || \
    echo "[UYARI] install-prereqs bazı adımlarda uyarı verdi; devam ediliyor."
else
  echo "[UYARI] install-prereqs-ubuntu.sh bulunamadı; MAVProxy'yi .venv kuracak."
fi
# PATH güncellemesi için profili yükle (varsa)
# shellcheck disable=SC1090
source "${HOME}/.profile" 2>/dev/null || true
tamam "Ön gereksinimler adımı tamamlandı."

bilgi "4/6 ArduPlane SITL derleniyor (15-30 dk sürebilir)..."
cd "$ARDUPILOT_DIZIN"
./waf configure --board sitl
./waf plane
tamam "ArduPlane SITL derlendi."

bilgi "5/6 Repo sanal ortamı (.venv) oluşturuluyor..."
cd "$REPO_KOK"
if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
tamam "Sanal ortam ve Python bağımlılıkları kuruldu."

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
