# YouTube Agent Skills — SHP entegrasyon haritası

Kaynak: https://github.com/Jakeschincariol/youtube-agent-skill
Lisans: MIT. Seçilen skill talimatları ve yardımcı Python araçları proje-yerel Claude Code skill'leri olarak eklendi.

## Karar
SHP'nin mevcut 14 motorlu Script Agent V2 zincirini değiştirmeden, üretim sonrası ve yayın paketi eksiklerini tamamlayan 9 skill kaydedildi.

| Skill | SHP eşleşmesi | Diğer repo eşleşmesi | Karar |
|---|---|---|---|
| yt-package | story_score / CEO Reviewer sonrasında başlık + thumbnail metni eş kontrolü | AITUBE2, Nobody-Tells-You, secret-history-plants | Kaydedildi |
| yt-retention | retention_engine tahmini ile gerçek YouTube Studio retention CSV'sini karşılaştırma | Yayındaki tüm kanallar | Kaydedildi |
| yt-edit | SHP script/subtitle çıktısından edit karar listesi; transcript gerekir | Özellikle AITUBE2 ve kanal video pipeline'ları | Kaydedildi |
| yt-chapters | subtitle.srt / transcript'ten geçerli YouTube chapters | Upload açıklaması üreten kanallar | Kaydedildi |
| yt-shorts | uzun video transcript'inden bağımsız Shorts adayları | AITUBE2 ve diğer uzun video kanalları | Kaydedildi |
| yt-seo | description, arama sorgusu ve tags son kontrolü | Tüm kanallar | Kaydedildi |
| yt-comment | yorum sınıflandırma ve marka sesinde cevap taslağı | Yayındaki tüm kanallar | Kaydedildi |
| yt-plan | üretim kapasitesine göre haftalık yayın planı | Tüm kanallar | Kaydedildi |
| yt-viral | her kanalın kendi medyanına göre outlier bulma; niche_intelligence / competitor_analyzer için tamamlayıcı | SHP'nin yönettiği kanallar | Kaydedildi |

## Bilinçli olarak eklenmeyenler
- yt-script: SHP'de Generator, Story DNA, Retention, Script Doctor ve CEO Reviewer zaten var. Skill'in 21 hook formülü ve hookscore.py aracı bağımsız testte kıyaslanabilir; mevcut motorların yerine geçirilmedi.
- yt-audit: SHP channel_analyzer, competitor_analyzer, decision_engine_v2 ve CEO Reviewer ile büyük ölçüde örtüşüyor. Tek-fix denetim yaklaşımı mevcut karar raporlarına sonradan eklenebilir; ayrı skill olarak çoğaltılmadı.

## Diğer repolara göre kullanım
- AITUBE2: yt-package, yt-edit, yt-chapters, yt-shorts, yt-seo en doğrudan fayda sağlar; çünkü repo script, voice, subtitles, render, thumbnail ve upload zincirine sahip.
- Nobody-Tells-You ve secret-history-plants: yt-package, yt-retention, yt-chapters, yt-seo ve yt-comment yayın sonrası iyileştirme için uygundur; mevcut repolarda transcript/analytics girdisinin varlığı ayrıca kontrol edilmelidir.
- SHP Engine: yt-viral, yt-retention ve yt-package araştırma/karar/üretim kalite kapılarına tamamlayıcıdır; mevcut motorları değiştirmez.

## Önemli sınırlar
- Bu skill'ler Claude Code'a talimat ve yerel yardımcı araç sağlar; SHP GitHub Actions otomasyonuna kendiliğinden bağlanmaz.
- Gerçek retention için YouTube Studio CSV dışa aktarımı gerekir; public YouTube Data API bunu vermez.
- yt-edit ve yt-chapters gerçek zaman damgalı transcript/SRT/VTT ister.
- yt-shorts aday ve kesim önerisi üretir; medya dosyasını otomatik kesmez.
- yt-package thumbnail görselini üretmez; metin/başlık eşleşmesini denetler.
- yt-viral public liste verisiyle çalışır; kanal başına en az dört video gerekir ve formül sınıflandırması nedensellik kanıtı değildir.
- Hiçbir skill otomatik yayınlama yetkisi almaz. Mevcut insan onayı ve yayın kapıları korunur.

## Güvenli deneme sırası
1. yt-package + yt-retention ile mevcut bir video çıktısını değerlendir.
2. yt-chapters / yt-edit / yt-shorts'u gerçek SRT üzerinde dene.
3. yt-seo ve yt-comment'u yayın paketi sonrası kullan.
4. yt-viral'i SHP niş araştırmasıyla aynı örneklem üzerinde karşılaştır.
5. Ölçülmüş kalite artışı olmadan SHP Python pipeline'ına kod entegrasyonu yapma.
