# Uçuş Numaraları ve Çakışmayı Önleme (UCUS_NUMARALARI.md)

> 🧭 **Başvuru belgesi** (sıralı akışın parçası değil) · [Yol haritası](../README.md#yol-haritası--neyi-hangi-sırayla)
>
> **Herkes bir kez baştan sona okusun.** Üretime başlamadan önce okunması
> gereken tek "kural" belgesi budur; 5 dakika sürer.

---

## 1. Kısaca (özet kutusu)

- Her uçuşun bir **adı** vardır: `F<numara>_<tür>` → ör. `F101_normal`, `F205_spoof_cmd`.
- **Numara, uçuşun kimliğidir.** Tüm ekipte her numara **bir kez** kullanılır.
- Her cihazın kendine ait bir **numara aralığı** vardır (pc1 → 100–199 …).
  Kimse başkasının aralığından numara kullanmaz.
- Aralık `config.yaml`'da yazar. Kurulumda **bir kez** ayarlanır.
- Hangi numarayı kullanacağını bilmiyorsan şunu çalıştır, sana söylesin:
  ```bash
  python betikler/ortak.py --sonraki normal      # veya spoof_cmd, flood ...
  ```
- Yanlış numara verirsen betikler artık **hiçbir şey başlatmadan durur** ve
  Türkçe olarak neyin yanlış olduğunu ve doğru numarayı söyler.

---

## 2. Neden bu kadar önemli?

Herkes verileri **kendi bilgisayarında** üretiyor. Sonunda hepsi tek bir
klasörde birleştirilecek ([VERI_PAYLASIMI.md](VERI_PAYLASIMI.md)):

```
Batuhan'ın PC'si          Arkadaş 2'nin PC'si        Arkadaş 3'ün PC'si
veri/ucuslar/             veri/ucuslar/              veri/ucuslar/
  F101_normal/              F201_normal/               F301_normal/
  F102_normal/              F202_flood/                F302_replay/
        \                        |                        /
         \______________________ | ______________________/
                                 v
                    ORTAK KLASÖR: ucuslar/
                      F101_normal/  F102_normal/
                      F201_normal/  F202_flood/
                      F301_normal/  F302_replay/
```

Her uçuş bir **klasördür** ve klasörün adı uçuşun adıdır. Peki iki kişi aynı
adı üretirse ne olur?

```
Batuhan:  F101_normal/   (gorev1, rüzgâr yok)
Arkadaş:  F101_normal/   (gorev3, rüzgârlı)      ← AYNI AD!
                    |
                    v  birleştirme
ORTAK:    F101_normal/   ← Hangisi? İkincisi kopyalanınca birincinin
                           üzerine yazar. Bir uçuş SESSİZCE KAYBOLUR.
```

Daha kötüsü: kopyalama klasör klasör değil dosya dosya olursa iki uçuşun
dosyaları **karışabilir**. Bir uçuşun `paketler.parquet`'i ötekinin
`ground_truth.json`'u ile yan yana kalır, etiketler yanlış çıkar ve model
hatalı veriyle eğitilir. Bu hatayı sonradan fark etmek çok zordur.

Aynı numara **aynı cihazda** iki kez kullanılırsa da sorun var: yeni kayıt
eski uçuşun klasörüne yazılır, eski veri bozulur.

**Çözüm basit:** her numara ekip genelinde **tek** olsun.

---

## 3. Uçuş adı nasıl okunur?

```
F 1 0 7 _ spoof_cmd
│ └─┬─┘   └───┬───┘
│   │         └── TÜR: normal, spoof_cmd, impersonation, replay, flood, fake_telemetry
│   └──────────── NUMARA: yüzler basamağı hangi PC olduğunu söyler (1xx = pc1)
└──────────────── "Flight" (uçuş) harfi, hep büyük F
```

Kurallar:

1. Büyük `F` ile başlar, ardından numara, `_`, tür gelir.
2. **Tür** yukarıdaki 6 kelimeden biri olmalı. Saldırılı uçuşta tür, yapılan
   saldırının adıyla **aynı** olmalı (`spoof_cmd` saldırısı → `F…_spoof_cmd`).
3. **Numara uçuşun kimliğidir; tür değil.** `F107_normal` ile `F107_flood`
   **ikisi birden olamaz**: 107 bir kez kullanıldıysa bitti, türü ne olursa olsun.
4. Numaralar sırayla gider: 100, 101, 102 … Arada boşluk kalması (ör. hatalı
   bir uçuşu silip numarasını atlamak) **sorun değildir**.

---

## 4. Kimin hangi aralığı var?

| `pc_id` | Makine | `ucus_no_araligi` | Kullanacağı adlar | Toplu üretim ana tohumu |
|---------|--------|-------------------|-------------------|-------------------------|
| `pc1` | Batuhan masaüstü (Pop!_OS 24.04) | `[100, 199]` | F100 … F199 | 101 |
| `pc2` | Şeyma laptop (Ubuntu 26.04) | `[200, 299]` | F200 … F299 | 102 |
| `pc3` | Hasan laptop (Ubuntu 26.04) | `[300, 399]` | F300 … F399 | 103 |
| `pc4` | Yusuf laptop (Ubuntu 26.04) | `[400, 499]` | F400 … F499 | 104 |
| `pc5` | Batuhan laptop | `[500, 599]` | F500 … F599 | 105 |

- Ekip 4 kişi, 5 makinedir. `pc_id` **kişiyi değil cihazı** gösterir: Her makinenin kendi
  `pc_id`'si ve kendi yüzlük bloğu vardır. Aynı kişinin iki makinesi de ayrı `pc_id` alır.
- Yüzlük blok `pc_id`'den gelir: `pcN` → N×100 ile N×100+99 arası. Aralığın bu bloğun
  **içinde** olması zorunludur; betikler bunu denetler.
- Yeni makine eklenirse sıradaki `pc_id` verilir (`pc6` → 600–699). Numaraları bölmeye gerek yok.
- Tablo değişirse **bu tabloyu güncelleyin** ve ekibe haber verin; tablo tek doğru kaynaktır.
- Ana tohum her makinede farklı olmalıdır: Aynı tohum aynı uçuş planını üretir.

> Neden 100 numara? Plan makine başına 90 uçuştur (toplam 450); kalan 10 numara başarısız
> uçuşlara yeter. Aralık dolarsa betik Türkçe uyarır. Kendi başınıza başka bloğa geçmeyin.

---

## 5. Kurulumda bir kez yapılacak ayar (adım adım)

1. Repo kök klasöründeki `config.yaml`'ı bir metin düzenleyiciyle açın.
2. Şu iki satırı **kendi satırınıza** (4. bölümdeki tablo) göre değiştirin:
   ```yaml
   pc_id: pc2
   ucus_no_araligi: [200, 299]
   ```
   Dosyadaki **başka hiçbir satırı** değiştirmeyin (portlar vb. herkeste aynı).
3. Kaydedin ve kontrol edin:
   ```bash
   source .venv/bin/activate
   python betikler/kontrol.py
   ```
   Şuna benzer bir satır görmelisiniz:
   ```
   [TAMAM] config.yaml okundu (pc_id=pc2, uçuş aralığı=F200-F299). Bu cihaz YALNIZCA bu aralıktaki numaraları kullanmalı.
   ```
   `pc_id`'yi değiştirip aralığı unuttuysanız burada HATA çıkar.

> ⚠️ **`config.yaml` git'te takip edilen bir dosyadır.** Kendi ayarınızı
> **commit'lemeyin / push'lamayın**, yoksa herkesin ayarı sizinkiyle
> değişir. Güvenli yol: ayarı yaptıktan sonra bir kez şunu çalıştırın:
> ```bash
> git update-index --skip-worktree config.yaml
> ```
> Böylece git sizin yerel değişikliğinizi görmezden gelir ve `git pull`
> onu ezmez. (Geri almak için: `git update-index --no-skip-worktree config.yaml`.)

---

## 6. Her uçuşta: numara nasıl seçilir?

En kolay yol, betiğe sormak:

```bash
python betikler/ortak.py --sonraki normal
# çıktı: F203_normal

python betikler/ortak.py --sonraki spoof_cmd
# çıktı: F203_spoof_cmd
```

Bu komut kendi `veri/ucuslar/` klasörünüze bakar, **kendi aralığınızdaki en
büyük numaranın bir fazlasını** verir. Sonra o adı üretim komutuna yazın:

```bash
bash betikler/normal_uretim.sh F203_normal gorevler/gorev1_dikdortgen.waypoints 180 3 90
```

> 📌 Belgelerdeki örnek komutlar (`F101_normal`, `F106_spoof_cmd` …) **pc1
> numaralarıdır**. Başka makinedeyseniz aynen kopyalamayın; numarayı kendi
> aralığınızdan seçin. Yanlışlıkla kopyalarsanız betik zaten durdurur.

Bir adın uygun olup olmadığını önceden denemek isterseniz:

```bash
python betikler/ortak.py --kontrol F203_normal --yeni
```

---

## 7. Betikler sizi nasıl koruyor? (otomatik kontroller)

`normal_uretim.sh` ve `saldiri_uret.sh` **hiçbir şeyi başlatmadan önce** uçuş
adını denetler. `kayit_proxy.py` ve `ucus_yap.py` elle çalıştırıldığında da
aynı denetim yapılır. Denetlenenler:

| # | Kontrol | Yakaladığı hata |
|---|---------|-----------------|
| 1 | `config.yaml` tutarlı mı? (`pc_id` ↔ aralık) | `pc_id: pc2` yapıp aralığı `[100,199]` bırakmak |
| 2 | Ad biçimi `F<numara>_<tür>` mi? | `101_normal`, `f101_normal`, `F101-normal` |
| 3 | Tür geçerli mi, saldırıyla uyumlu mu? | `F106_normal` adıyla spoof_cmd saldırısı |
| 4 | Numara bu cihazın aralığında mı? | pc2'de `F101_normal` (belge örneğini kopyalamak) |
| 5 | Bu numara daha önce kullanılmış mı? | `F101_normal` varken `F101_normal` veya `F101_flood` |

Sorun varsa şöyle bir mesaj görürsünüz ve **hiçbir kayıt başlamaz**:

```
[HATA] F101 bu cihazın numara aralığında DEĞİL. config.yaml: pc_id=pc2,
ucus_no_araligi=[200, 299]. Başka bir cihazın numarasını kullanırsanız veriler
birleşirken uçuşlar birbirinin üzerine yazılır. Bu cihaz için sıradaki boş ad:
F203_normal. Ayrıntı: belgeler/UCUS_NUMARALARI.md
```

Mesajdaki **"sıradaki boş ad"**ı kullanıp komutu tekrar çalıştırmanız yeterli.

> Kontrol yalnızca **kendi bilgisayarınızdaki** klasörlere bakabilir;
> başkasının bilgisayarını göremez. Cihazlar arası çakışmayı önleyen şey
> **aralıkların ayrı olmasıdır**. Bu yüzden 5. bölümdeki ayar kritik.

---

## 8. Sık karşılaşılan durumlar

**Uçuş yarıda kaldı / hatalı oldu, aynı numarayla tekrar uçurmak istiyorum.**
Önce bozuk uçuşu silin, sonra aynı adla tekrar çalıştırın:
```bash
rm -rf veri/ucuslar/F203_normal
bash betikler/normal_uretim.sh F203_normal ...
```
Ya da silmeden yeni numaraya geçin (F204). İkisi de doğrudur; numara atlamak
sorun değildir. **Emin değilseniz silmeyin, yeni numara alın.**

**"numarası zaten kullanılmış" hatası aldım ama o uçuş iyi.**
Doğru davranış bu: betik eski uçuşunuzu korudu. Mesajdaki sıradaki boş adı
kullanın.

**Yeni bir makinede de üretim yapacağım.**
O makineye 4. bölümdeki tablodan kendi `pc_id`'sini verin. Aynı `pc_id` iki makinede
kullanılmaz.

**Bilgisayarımı değiştirdim / repoyu yeniden klonladım.**
Yeni klonda `veri/ucuslar/` boştur (veri git'te yok), betik bu yüzden yeniden
F100'den başlamak isteyebilir. Eski cihazdaki uçuşları ya yeni cihaza kopyalayın
ya da ortak klasörde kullanılmış son numaraya bakıp `config.yaml`'daki aralığın
alt sınırını onun bir fazlasına çekin (ör. `[118, 199]`).

**`replay` saldırısı için kaynak uçuş başka birine ait.**
`--kaynak-ucus` olarak **kendi** bilgisayarınızdaki bir normal uçuşu verin.
Replay'in kaynağı ile hedefi farklı numaralardır; kaynak uçuşun numarası
kullanıldığı için hata vermez.

**Aralığım doldu.**
Betik "aralığı doldu" der. Kendi başınıza başka bir bloğa **geçmeyin**; ekiple
yeni bir blok kararlaştırıp 4. bölümdeki tabloyu güncelleyin.

---

## 9. Birleştirirken son güvenlik adımı

Ortak klasöre kopyalarken **asla üzerine yazmayan** komut kullanın:

```bash
# Var olan klasör/dosyaya dokunmaz, yalnızca yenileri ekler
rsync -av --ignore-existing veri/ucuslar/ /ortak/klasor/ucuslar/
```

Bulut klasörüne (Drive vb.) sürükle-bırak yapıyorsanız ve "dosya zaten var,
değiştirilsin mi?" sorusu çıkarsa **HAYIR deyin ve ekibe haber verin**; bu bir
çakışma demektir.

Birleştirdikten sonra aynı numaranın iki kez geçip geçmediğini kontrol edin:

```bash
ls /ortak/klasor/ucuslar | cut -d_ -f1 | sort | uniq -d
# Hiçbir şey yazmamalı. Bir numara yazarsa o numara iki kez kullanılmış demektir.
```

---

## 10. Asistan (Claude Code vb.) kullananlar için

Repo kökündeki `AGENTS.md` bu kuralları asistanınıza da anlatır. Asistan,
oturum başında `config.yaml`'daki `pc_id` ve aralığın hangi cihaz olduğunuzla
uyuştuğunu sizinle kontrol eder. Yine de bir kez bu belgeyi kendiniz okuyun.
