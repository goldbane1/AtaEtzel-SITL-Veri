# AtaEtzel — SITL MAVLink Veri Üretimi

Sabit kanatlı İHA'lar için **MAVLink haberleşmesine yönelik siber saldırı tespiti**
projesinin **veri üretimi** bölümüdür. ArduPlane SITL simülasyonunda normal ve
(yalnızca simülasyon içi) saldırılı uçuşlar üretir, MAVLink trafiğini bir kayıt
proxy'si ile kaydeder, etiketler ve öznitelik çıkarır. Amaç, ileride eğitilecek
**savunma amaçlı** bir saldırı tespit (IDS) / MAVLink güvenlik duvarı modeli için
etiketli bir veri seti hazırlamaktır.

> **Kapsam:** Bu repo yalnızca veri üretir. Tespit modeli ve panel bu reponun
> dışındadır.

---

## Yol haritası — neyi hangi sırayla?

Proje **beş aşamadan** oluşur. Sırayı bozmayın: bir aşama bitmeden sonrakine
geçmeyin. Her aşamada okunacak belge ve çalıştırılacak komut aşağıda.

| # | Aşama | Ne yaparsınız | Belge | Ana komut |
|---|-------|---------------|-------|-----------|
| 1 | **Kurulum** | ArduPlane + bağımlılıkları kurar | [KURULUM.md](belgeler/KURULUM.md) | `bash setup.sh` |
| 2 | **Sağlık kontrolü** | Kurulum eksiksiz mi, doğrular | [KURULUM.md](belgeler/KURULUM.md) | `python betikler/kontrol.py` |
| 3 | **Veri üretimi** | Normal + saldırılı uçuşlar üretir | [VERI_URETIMI.md](belgeler/VERI_URETIMI.md) | `normal_uretim.sh` / `saldiri_uret.sh` |
| 4 | **İşleme** | Etiketler, öznitelik çıkarır, böler, doğrular | [VERI_URETIMI.md](belgeler/VERI_URETIMI.md) | `etiketle → oznitelik → bol → dogrula` |
| 5 | **Paylaşım** | Üç makinenin verisini birleştirir | [VERI_PAYLASIMI.md](belgeler/VERI_PAYLASIMI.md) | — |

**Her an başvurulabilecek (sıralı değil) belgeler:**

- [VERI_SEMASI.md](belgeler/VERI_SEMASI.md) — dosya/sütun sözleşmesi. Betikler
  buna uyar; bir çıktı "yanlış" görünüyorsa önce buraya bakın.
- [SORUN_GIDERME.md](belgeler/SORUN_GIDERME.md) — bir komut hata verirse ilk
  durağınız.
- [UCUS_NUMARALARI.md](belgeler/UCUS_NUMARALARI.md) — uçuş adları, kimin hangi
  numara aralığını kullandığı ve çakışmanın nasıl önlendiği. **Üretimden önce
  bir kez mutlaka okunur.**

> **İlk kez mi kuruyorsunuz?** Aşağıdaki *Hızlı başlangıç* (Aşama 1–2) ile
> başlayın; sonra Aşama 3 için [VERI_URETIMI.md](belgeler/VERI_URETIMI.md)'ye
> geçin.

---

## Hızlı başlangıç

```bash
# 1) Klonla ve kur (ArduPlane Plane-4.7.2 derlenir; 15-30 dk)
git clone <repo-adresi> && cd AtaEtzel-SITL-Veri
bash setup.sh

# 2) Sağlık kontrolü
source .venv/bin/activate
python betikler/kontrol.py        # hepsi TAMAM olmalı

# 3) config.yaml'da pc_id ve ucus_no_araligi'nı KENDİ cihazına göre ayarla
#    (bkz. belgeler/UCUS_NUMARALARI.md)
```

Ayrıntılar: [belgeler/KURULUM.md](belgeler/KURULUM.md).

### Desteklenen işletim sistemleri

Ubuntu **22.04 / 24.04 / 26.04** ve bunlara dayanan **Pop!_OS** desteklenir
(WSL2 dahil). Ubuntu 20.04 ve öncesi desteklenmez; `setup.sh` bu durumda
Türkçe uyarı verip durur. ArduPlane sürümü (Plane-4.7.2) tüm makinelerde aynı
olduğu sürece makinelerin farklı Ubuntu sürümünde olması üretilen veriyi
etkilemez.

> ⚠️ **Ubuntu 26.04 hakkında (henüz denenmedi):** `setup.sh` 26.04'te de
> çalışacak şekilde ayarlandı, ancak bu sürümde **gerçek bir kurulum ve
> derleme henüz yapılmadı**. Bilinen riskler:
>
> - 26.04 daha yeni bir derleyici (GCC) ile gelir. Plane-4.7.2 bu derleyiciden
>   önce yayımlandığı için `./waf plane` adımında daha önce görülmemiş
>   uyarılar ya da hatalar çıkabilir.
> - ArduPilot'un `install-prereqs-ubuntu.sh` betiği 26.04'ün kod adını
>   tanımazsa `setup.sh` durmaz, temel paketleri yedek adımla kurar. Ancak bu
>   durumda derlemenin ihtiyaç duyduğu bazı Python paketleri eksik kalabilir.
>
> 26.04 kullanıyorsanız `bash setup.sh` çıktısının tamamını (özellikle
> `[UYARI]`/`[HATA]` satırlarını) kaydedin ve hata çıkarsa ekiple paylaşın.
> Çözüm bulununca bu not ve [SORUN_GIDERME.md](belgeler/SORUN_GIDERME.md)
> güncellenecek. İşletim sistemini sonradan yükseltirseniz (ör. 24.04 → 26.04)
> şu komutu yeniden çalıştırın:
> `cd ~/ardupilot && Tools/environment_install/install-prereqs-ubuntu.sh -y`

---

## Bir uçuş üretmek

SITL'yi ayrı bir terminalde başlatın:

```bash
cd ~/ardupilot/ArduPlane && sim_vehicle.py -v ArduPlane --no-mavproxy
```

**Normal uçuş** (tek komut):

```bash
bash betikler/normal_uretim.sh F101_normal gorevler/gorev1_dikdortgen.waypoints 180 3 90
```

**Saldırılı uçuş** (tek komut, örn. sahte komut 60. sn'de 30 sn):

```bash
bash betikler/saldiri_uret.sh F106_spoof_cmd gorevler/gorev1_dikdortgen.waypoints spoof_cmd 180 30 60
```

**İşleme** (etiketle → öznitelik → böl → doğrula):

```bash
python betikler/etiketle.py --hepsi
python betikler/oznitelik.py --hepsi
python betikler/bol.py
python betikler/dogrula.py --hepsi
```

Uçtan uca oturum: [belgeler/VERI_URETIMI.md](belgeler/VERI_URETIMI.md).

---

## Klasör yapısı ve betikler

```
betikler/           Python kodları
  ortak.py          Ortak yardımcılar + GÜVENLİK kontrolü (localhost)
  kontrol.py        Kurulum sağlık kontrolü
  kayit_proxy.py    MAVLink kayıt proxy'si (projenin kalbi)
  ucus_yap.py       Otomatik normal uçuş (yer istasyonu rolü)
  normal_uretim.sh  Tek komutla normal uçuş
  saldiri_uret.sh   Tek komutla saldırılı uçuş
  etiketle.py       Paketleri ground_truth'a göre etiketler
  oznitelik.py      1 sn'lik öznitelik pencereleri çıkarır
  bol.py            egitim/dogrulama/test bölmesi (veri/bolme.csv)
  dogrula.py        Uçuş klasörü eksiksizlik/tutarlılık kontrolü
  saldirilar/       5 saldırı betiği (hepsi yalnızca localhost)
gorevler/           5 waypoint görev dosyası (.waypoints)
belgeler/           Türkçe rehberler
veri/               Ham/işlenmiş veri (git'e girmez; veri/ornek/ hariç)
config.yaml         pc_id, portlar, aralıklar
setup.sh            Baştan sona kurulum
```

| Betik | Görevi |
|-------|--------|
| `kontrol.py` | Kurulumun eksiksizliğini TAMAM/HATA olarak raporlar |
| `kayit_proxy.py` | İki yöndeki her MAVLink paketini kaydeder |
| `ucus_yap.py` | Görev yükler, arm/AUTO/kalkış yapar, uçurur |
| `etiketle.py` | Her pakete `label` ekler (normal / saldırı türü) |
| `oznitelik.py` | 1 sn pencere öznitelikleri → `pencereler.parquet` |
| `bol.py` | Uçuş düzeyinde katmanlı bölme |
| `dogrula.py` | Her uçuş için TAMAM/EKSİK raporu |

---

## Üç bilgisayar düzeni ve uçuş numaraları

> ⚠️ **Üretime başlamadan önce herkes okusun:**
> [belgeler/UCUS_NUMARALARI.md](belgeler/UCUS_NUMARALARI.md). Uçuş numarası
> çakışırsa veriler birleştirilirken bir uçuş **sessizce kaybolur**.

Her uçuşun adı `F<numara>_<tür>` biçimindedir ve **numara tüm ekipte bir kez**
kullanılır. Bunun için her kişiye bir yüzlük blok, her **cihaza** bu blok içinde
ayrı bir aralık verilir. Her cihaz `config.yaml`'da yalnızca `pc_id` ve
`ucus_no_araligi`'nı ayarlar.

| Kişi / cihaz | `pc_id` | `ucus_no_araligi` | Örnek |
|--------------|---------|-------------------|-------|
| Batuhan — masaüstü | `pc1` | `[100, 149]` | `F101_normal` |
| Batuhan — laptop | `pc1` | `[150, 199]` | `F151_flood` |
| 2. kişi | `pc2` | `[200, 299]` | `F205_spoof_cmd` |
| 3. kişi | `pc3` | `[300, 399]` | `F312_flood` |

- Sıradaki boş adı öğrenmek için: `python betikler/ortak.py --sonraki normal`
- Üretim betikleri yanlış/kullanılmış bir numarada **hiçbir şey başlatmadan
  durur** ve doğru adı söyler.
- Belgelerdeki örnek komutlar pc1 numaralarıyla yazılmıştır; pc2/pc3 kendi
  numarasını kullanır.

Veri birleştirme: [belgeler/VERI_PAYLASIMI.md](belgeler/VERI_PAYLASIMI.md).

---

## Etik ve kapsam

- **Saldırı betikleri yalnızca `127.0.0.1` (localhost) hedefine bağlanır.** Bu
  kontrol `ortak.py`'de zorunludur; hedef farklıysa betik Türkçe hata verip çıkar.
  Betikler **yalnızca kendi simülasyonumuz içindir**, gerçek sistemlerde
  kullanılmaz ve dış ağa çıkamaz.
- Bu, bir **savunma** (saldırı tespiti) sistemi için veri üretir.
- Ham uçuş verisi (parquet/tlog/BIN) git'e konmaz; `.gitignore` bunu engeller.

---

## Sürüm ve tekrar üretilebilirlik

- ArduPlane **Plane-4.7.2** (üç makinede de aynı). Farklı sürüm sonuçları tekrar
  üretilemez kılar.
- `--speedup` **kullanılmaz**: paketler arası süreleri bozar; zamanlama
  öznitelikleri buna dayanır.

Sorun giderme: [belgeler/SORUN_GIDERME.md](belgeler/SORUN_GIDERME.md) ·
Veri şeması: [belgeler/VERI_SEMASI.md](belgeler/VERI_SEMASI.md)
