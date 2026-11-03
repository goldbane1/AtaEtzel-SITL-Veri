# Veri Paylaşımı (VERI_PAYLASIMI.md)

Üç bilgisayarda üretilen uçuşlar tek bir veri setinde birleştirilir. Ham veri
git'e **konmaz**; bu rehber nasıl paylaşılacağını anlatır.

## Neden git'e konmuyor?

`paketler.parquet`, `*.tlog` ve `*.BIN` dosyaları büyüktür ve hızla büyür.
`.gitignore` bunları dışlar. Repoda yalnızca **kod, belge ve çok küçük örnek
veri** (`veri/ornek/`) bulunur.

Her push'tan önce:

```bash
git status            # veri/ucuslar/ altındaki ağır dosyalar GÖRÜNMEMELİ
```

Yanlışlıkla eklendiyse geçmişten temizlenmesi gerekir (ekibe/Claude Code'a bildirin).

## Dosya adları neden çakışmıyor?

Her makine ayrı bir uçuş numarası aralığı kullanır:

| Bilgisayar | `pc_id` | Aralık |
|-----------|---------|--------|
| 1. PC | `pc1` | F100–F199 |
| 2. PC | `pc2` | F200–F299 |
| 3. PC | `pc3` | F300–F399 |

Böylece `F101_normal` (pc1) ile `F201_normal` (pc2) çakışmaz. Her kişi
`config.yaml`'da yalnızca kendi `pc_id` ve `ucus_no_araligi`'nı ayarlar.

## Birleştirme yöntemi (önerilen)

1. Ortak bir bulut klasörü açın (Google Drive, OneDrive veya kurumsal sunucu).
   Yapı repodaki ile **aynı** olsun:
   ```
   AtaEtzel-veri/
     ucuslar/
       F101_normal/ ...
       F205_spoof_cmd/ ...
       F312_flood/ ...
   ```
2. Her kişi kendi `veri/ucuslar/F?xx_*` klasörlerini bu ortak klasöre yükler.
   Numara aralıkları çakışmadığı için üzerine yazma olmaz.
3. Birleştirme makinesinde tüm uçuşları tek bir `veri/ucuslar/` altında toplayıp
   işleme adımlarını (etiketle → öznitelik → böl → doğrula) **birlikte** çalıştırın:
   ```bash
   python betikler/etiketle.py --hepsi
   python betikler/oznitelik.py --hepsi
   python betikler/bol.py
   python betikler/dogrula.py --hepsi
   ```
   Böylece `pencereler.parquet` ve `bolme.csv` üç makinenin verisini birlikte kapsar.

## Örnek veri (`veri/ornek/`)

Çok küçük bir örnek uçuş (ör. birkaç saniyelik) `veri/ornek/` altına konabilir ve
`.gitignore` istisnası sayesinde git'e girer. Bu, repoyu klonlayan birinin şemayı
gerçek veri üretmeden görmesini sağlar. Büyük dosyaları buraya **koymayın**.
