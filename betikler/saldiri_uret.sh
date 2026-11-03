#!/usr/bin/env bash
# =====================================================================
# saldiri_uret.sh — Tek komutla bir SALDIRILI uçuş üretir.
# ---------------------------------------------------------------------
# Normal uçuşı tekrar uçururken, uçuşın ORTASINDA seçilen saldırıyı
# çalıştırır. Böylece saldırıdan ÖNCE ve SONRA temiz (normal) bölümler
# kalır; bu, etiketleme ve model eğitimi için önemlidir.
#
# SITL'nin AYRI bir terminalde çalıştığını varsayar.
#
# Kullanım:
#   bash betikler/saldiri_uret.sh <ucus_id> <gorev> <saldiri> [sure] [saldiri_sure] [gecikme] [ekstra...]
# Örnek (sahte komut, 60. sn'de 30 sn):
#   bash betikler/saldiri_uret.sh F106_spoof_cmd gorevler/gorev1_dikdortgen.waypoints spoof_cmd 180 30 60
# Örnek (replay, kaynak uçuş ek argümanı):
#   bash betikler/saldiri_uret.sh F208_replay gorevler/gorev2_uzunhat.waypoints replay 180 30 60 --kaynak-ucus F101_normal
#
# Geçerli saldırılar: spoof_cmd impersonation replay flood fake_telemetry
# =====================================================================
set -euo pipefail

UCUS="${1:-}"
GOREV="${2:-}"
SALDIRI="${3:-}"
SURE="${4:-180}"
SALDIRI_SURE="${5:-30}"
GECIKME="${6:-60}"
shift 6 2>/dev/null || true
EKSTRA=("$@")   # saldırıya özgü ek argümanlar (ör. --kaynak-ucus, --hiz)

if [[ -z "$UCUS" || -z "$GOREV" || -z "$SALDIRI" ]]; then
  echo "[HATA] Kullanım: bash betikler/saldiri_uret.sh <ucus_id> <gorev> <saldiri> [sure] [saldiri_sure] [gecikme] [ekstra...]"
  exit 1
fi

SALDIRI_BETIK="betikler/saldirilar/${SALDIRI}.py"
KOK="$(cd "$(dirname "$0")/.." && pwd)"
cd "$KOK"

if [[ ! -f "$SALDIRI_BETIK" ]]; then
  echo "[HATA] Saldırı betiği bulunamadı: $SALDIRI_BETIK"
  echo "       Geçerli: spoof_cmd impersonation replay flood fake_telemetry"
  exit 1
fi

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo "[BILGI] 1/4 Kayıt proxy'si başlatılıyor (arka planda)..."
python betikler/kayit_proxy.py --ucus "$UCUS" &
PROXY_PID=$!
sleep 3

echo "[BILGI] 2/4 Uçuş başlatılıyor (arka planda): $GOREV, $SURE sn..."
python betikler/ucus_yap.py --gorev "$GOREV" --ucus "$UCUS" --sure "$SURE" &
UCUS_PID=$!

temizle() {
  echo "[BILGI] 4/4 Temizlik: uçuş ve proxy kapatılıyor..."
  kill -INT "$UCUS_PID" 2>/dev/null || true
  wait "$UCUS_PID" 2>/dev/null || true
  kill -INT "$PROXY_PID" 2>/dev/null || true
  wait "$PROXY_PID" 2>/dev/null || true
  echo "[TAMAM] Saldırılı uçuş üretimi bitti: $UCUS ($SALDIRI)"
}
trap temizle EXIT

echo "[BILGI] 3/4 $GECIKME sn sonra '$SALDIRI' saldırısı $SALDIRI_SURE sn çalışacak..."
python "$SALDIRI_BETIK" \
  --ucus "$UCUS" \
  --sure "$SALDIRI_SURE" \
  --baslangic-gecikme "$GECIKME" \
  "${EKSTRA[@]}"

# Saldırı bittikten sonra uçuşın temiz kuyruk bölümü için kısa bekleme
echo "[BILGI] Saldırı bitti; temiz kuyruk bölümü için uçuşın bitmesi bekleniyor..."
wait "$UCUS_PID" 2>/dev/null || true
