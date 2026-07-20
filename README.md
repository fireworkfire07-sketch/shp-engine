# SHP Engine

SHP Engine, verilen bir konudan otomatik dikey video oluşturan temel sistemdir.

## Şu anda çalışan bölüm

- Konuyu alır
- 6 sahnelik Türkçe içerik oluşturur
- Her sahne için 1080×1920 görsel üretir
- Sahne görsellerini birleştirir
- Gerçek `video.mp4` dosyası oluşturur
- Aynı klasöre `manifest.json` kaydeder
- YouTube gizlilik ayarını varsayılan olarak `private` tutar

## Kurulum

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Windows:

```bash
.venv\Scripts\activate
pip install -e .
```

## Sağlık kontrolü

```bash
shp-engine health
```

## Video üret

```bash
shp-engine run "Bitkilerin gizli iletişimi"
```

Çıktılar şu yapıda oluşur:

```text
output/
  20260720-120000-bitkilerin-gizli-iletisimi/
    video.mp4
    manifest.json
    frames/
```

## Şimdilik eksik olanlar

- Yapay zekâ ile uzun ve özgün senaryo üretimi
- Türkçe seslendirme
- Otomatik görsel/video klip bulma veya üretme
- Altyazı
- Müzik
- YouTube yükleme
- Zamanlanmış otomatik çalıştırma

Bu eksikler sonraki katmanlarda eklenecek. Mevcut sürüm gerçek MP4 üretir fakat sessiz, yazı tabanlı ilk çalışan sürümdür.

## Güvenlik

Gerçek API anahtarlarını repoya yazmayın. Anahtarları yalnızca `.env`, GitHub Secrets veya Vercel Environment Variables alanında saklayın.
