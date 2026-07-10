# SHP Engine

YouTube'da bir nişin son 90 gündeki en hızlı videolarını bulur, izlenme hızını ölçer ve **0-100 niş puanı** üretir.

## 1. Gereken tek anahtar

Google Cloud Console'da **YouTube Data API v3** etkinleştir ve bir API key oluştur.

Anahtarı GitHub'a yazma. Bilgisayarında terminale ekle.

### Windows PowerShell

```powershell
$env:YOUTUBE_API_KEY="BURAYA_API_KEY"
python commander.py "bitkilerin gizli tarihi"
```

### Windows kalıcı kayıt

```powershell
setx YOUTUBE_API_KEY "BURAYA_API_KEY"
```

`setx` kullandıktan sonra terminali kapatıp yeniden aç ve çalıştır:

```powershell
python commander.py "bitkilerin gizli tarihi"
```

## 2. Çıktı

Sistem otomatik olarak şu klasörü oluşturur:

```text
projects/bitkilerin-gizli-tarihi/
```

İçinde:

```text
analysis.json   Ham video verileri ve puan
report.md       Okunabilir niş raporu
```

## 3. Puanın anlamı

- **75-100:** GİR — güçlü talep var.
- **55-74:** TEST ET — önce 5-10 video ile doğrula.
- **0-54:** BEKLET — talep zayıf veya başarı birkaç kanalda toplanmış.

## Şu an gerçekten çalışan bölüm

- Son 90 gündeki en çok izlenen videoları çeker.
- Her videonun günlük izlenme hızını hesaplar.
- Kanal çeşitliliğini ölçer.
- Niş puanı ve aksiyon kararı verir.
- Markdown raporu üretir.

Henüz otomatik video üretmez ve YouTube'a yükleme yapmaz. Önce izlenen formatı bulmak için tasarlanmıştır.
