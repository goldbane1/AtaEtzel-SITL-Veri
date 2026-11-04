#!/usr/bin/env bash
# =====================================================================
# normal_uretim.sh — Tek komutla bir NORMAL uçuş üretir.
# ---------------------------------------------------------------------
# Bu betik kayit_proxy.py ve ucus_yap.py'yi birlikte çalıştırır.
# SITL'nin AYRI bir terminalde zaten çalıştığını varsayar:
#   cd ~/ardupilot/ArduPlane && sim_vehicle.py -v ArduPlane --no-mavproxy
#
# Kullanım:
#   bash betikler/normal_uretim.sh <ucus_id> <gorev_dosyasi> [sure] [ruzgar_hiz] [ruzgar_yon]
# Örnek:
#   bash betikler/normal_uretim.sh F101_normal gorevler/gorev1_dikdortgen.waypoints 180 3 90
# =====================================================================
set -euo pipefail

UCUS="${1:-}"
GOREV="${2:-}"
SURE="${3:-180}"
RUZGAR_HIZ="${4:-0}"
RUZGAR_YON="${5:-0}"

if [[ -z "$UCUS" || -z "$GOREV" ]]; then
  echo "[HATA] Kullanım: bash betikler/normal_uretim.sh <ucus_id> <gorev> [sure] [ruzgar_hiz] [ruzgar_yon]"
  exit 1
fi

# Repo kökü (bu betik betikler/ altında)
KOK="$(cd "$(dirname "$0")/.." && pwd)"
cd "$KOK"

# Sanal ortam varsa etkinleştir
if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Çakışma koruması: uçuş adı bu cihazın aralığında mı, daha önce kullanıldı mı?
# (Ayrıntı: belgeler/UCUS_NUMARALARI.md) Sorun varsa hiçbir şey başlatılmadan durur.
python betikler/ortak.py --kontrol "$UCUS" --yeni --tur normal || exit 1

echo "[BILGI] 1/3 Kayıt proxy'si başlatılıyor (arka planda)..."
python betikler/kayit_proxy.py --ucus "$UCUS" &
PROXY_PID=$!

# Proxy'nin ayağa kalkması için kısa bekleme
sleep 3

temizle() {
  echo "[BILGI] 3/3 Proxy kapatılıyor (PID $PROXY_PID)..."
  kill -INT "$PROXY_PID" 2>/dev/null || true
  wait "$PROXY_PID" 2>/dev/null || true
  echo "[TAMAM] Normal uçuş üretimi bitti: $UCUS"
}
trap temizle EXIT

echo "[BILGI] 2/3 Uçuş yapılıyor: $GOREV (sure=$SURE sn, ruzgar=$RUZGAR_HIZ m/s @ $RUZGAR_YON derece)..."
python betikler/ucus_yap.py \
  --gorev "$GOREV" \
  --ucus "$UCUS" \
  --sure "$SURE" \
  --ruzgar-hiz "$RUZGAR_HIZ" \
  --ruzgar-yon "$RUZGAR_YON"
