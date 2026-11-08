# G8 Veri Üretimi: Agent Komutları (G8_AGENT_KOMUTLARI.md)

> Gerçek veri üretimi için her makinede kodlama asistanına verilecek komut dizinidir.
> Kullanım: Aşağıdaki metni asistana yapıştırın, ilk satırdaki `pc_id`'yi kendi makinenize göre yazın.
> Plan ve hedef sayılar: [YOL_HARITASI.md](YOL_HARITASI.md) (G8). Numara kuralları:
> [UCUS_NUMARALARI.md](UCUS_NUMARALARI.md).

Her makine 90 uçuş üretir (40 normal, 50 saldırılı), yaklaşık 7 saat sürer. Beş makinede toplam 450
uçuş olur. Ekip makineleri **sadece uçuşları üretir** ve Batuhan'a gönderir; etiketleme ve sonraki
işlemeyi Batuhan birleşik veride yapar.

Üretim sırasında laptop şarja takılı ve kapağı açık kalmalı, aynı makinede başka SITL açılmamalıdır.

## Asistana verilecek metin

````text
Bu makine: pc_id = pcX  (kendi numaranı yaz, aşağıdaki tablodan)

AtaEtzel-SITL-Veri reposunda G8 veri üretimini başlat. Görevin sadece uçuş üretmek.
Etiketleme, öznitelik, bölme ve doğrulama YAPMA; onları Batuhan yapacak.
Kod veya config değiştirme, commit/push yapma. Herhangi bir adım beklenenden farklı
çıkarsa dur ve bana Türkçe söyle, kendi başına düzeltme.

Bu makinenin değerleri:
| pc_id | Makine           | ucus_no_araligi | ana tohum | deneme uçuşları |
| pc1   | Batuhan masaüstü | [100, 199]      | 101       | yok             |
| pc2   | Şeyma laptop     | [200, 299]      | 102       | F200, F201      |
| pc3   | Hasan laptop     | [300, 399]      | 103       | F300, F301      |
| pc4   | Yusuf laptop     | [400, 499]      | 104       | F400, F401      |
| pc5   | Batuhan laptop   | [500, 599]      | 105       | yok             |

1) Repoya gir, kodu güncelle:
   git status --short --branch     (dal veri-duzeltmeleri olmalı)
   git pull --ff-only origin veri-duzeltmeleri
   git checkout main YAPMA, bu dalda kal.
   Uçuş kodu ekipte aynı olmalı, şunu çalıştır:
   git diff --quiet d81610a HEAD -- betikler tests && echo KOD_AYNI
   KOD_AYNI yazmazsa dur ve sor.

2) config.yaml'daki pc_id ve ucus_no_araligi tablodakiyle aynı olmalı.

3) Deneme verisini sil (tabloda "yok" yazıyorsa bu adımı atla, ama veri/ucuslar boş olmalı):
   ls veri/ucuslar
   Listede sadece tablodaki iki deneme uçuşu olmalı. Başka uçuş varsa SİLME, dur ve sor.
   Sadece o iki klasörü sil, ardından deneme çıktılarını da sil:
   rm -f veri/oznitelikler/pencereler.parquet veri/bolme.csv
   rm -rf veri/bolmeler

4) Kontrol et:
   source .venv/bin/activate
   python betikler/kontrol.py      (hepsi TAMAM olmalı)
   pytest tests/ -q                (hata olmamalı)
   pgrep -x arduplane              (çıktı boş olmalı, açık SITL varsa dur ve sor)

5) Üretimi başlat. <TOHUM> yerine tablodaki ana tohumu, <PC> yerine pc_id'yi yaz:
   nohup python betikler/toplu_uretim.py --normal 40 --saldirili 50 \
     --kanal-profilleri temiz,hafif,orta,agir --ana-tohum <TOHUM> --no-isleme \
     > ~/g8_<PC>.log 2>&1 &

6) 2 dakika sonra ~/g8_<PC>.log dosyasına bir kez bak. "Üretim boyunca uyku engellendi"
   ve "Uçuş 1/90" satırları görünüyorsa bana "üretim başladı" de ve dur.
   Üretim yaklaşık 7 saat sürer; bekleme ve logu tekrar tekrar okuma.

Üretim bitince bana sorulduğunda (log sonunda "Toplam süre" görününce):
   tail -n 25 ~/g8_<PC>.log
   Üretilen/Başarısız sayılarını söyle.
   tar -czf ~/AtaEtzel_<PC>_ucuslar.tar.gz -C veri ucuslar
   sha256sum ~/AtaEtzel_<PC>_ucuslar.tar.gz
   Arşivin yolunu ve sha256 değerini bana ver. Bunu ve ~/g8_<PC>.log dosyasını Batuhan'a göndereceğim.
````

## Üretim bittikten sonra

- Arşivler ve loglar Batuhan'da toplanır. Birleştirme ve numara tekrarı denetimi için:
  [VERI_PAYLASIMI.md](VERI_PAYLASIMI.md).
- Başarısız uçuş sayısı yüksekse eksikler, aynı makinede **farklı bir ana tohumla** tamamlanır.
  Aynı tohum aynı planı üretir. Makine başına 10 yedek numara vardır.
