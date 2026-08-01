# SHP Engine

## Ne işe yarar

Bu repo, 3 YouTube kanalının (secret-history-plants, Nobody-Tells-You, AITUBE2) "beynidir": hangi konuların YouTube'da güçlü talep gördüğünü ölçer, uygun kanalı seçer ve o kanala **konu başlığı** yollar. Videoyu kendisi üretmez — script, ses, görsel, montaj ve upload her kanalın kendi reposunda olur (bkz. "İlgili repolar").

## Pipeline akışı

İki paralel akış var; ikisi de sonunda `projects/<slug>/analysis.json` üretir ama farklı script'lerle:

**A) Basit akış (otomatik, `dispatch.yml` kullanır)**

```
batch_research.py (sabit 5 konu listesi)
   → commander.py <konu>   (YouTube API'den son 90 gün, en hızlı videolar)
   → projects/<slug>/analysis.json + report.md   (0-100 niş puanı)
   → dispatcher.py   (75+ puanlı nişleri channels.json'daki anahtar kelimelerle kanala eşler)
   → repository_dispatch (new_topic)   → hedef kanal reposu
```

**B) PRO akış (manuel, `run-shp.yml` kullanır — tam SHP CEO zinciri)**

```
channel_analyzer.py + competitor_analyzer.py   (kendi kanal + rakip sağlığı)
   → niche_intelligence.py   (kendi kanal verisinden dinamik konu adayları üretir, YouTube'da tarar, en iyi 10'u sıralar)
   → story_report.py + story_score.py   (hikâye/başlık DNA puanı)
   → decision_engine_v2.py   (CEO kararı: yayınla/yayınlama, gerekçeli)
   → effort_filter.py   (emek/getiri değerlendirmesi)
   → growth_advisor.py   (yayın zamanı, hashtag, tutundurma planı)
   → script_agent_v2.py   (14 motorlu Head Writer AI — script, storyboard, altyazı, thumbnail metni, YouTube upload paketi üretir; GROQ_API_KEY yoksa kural-tabanlı yedek moda düşer)
```

`run-shp.yml` bu akışın çıktısını doğrudan bir kanala göndermez — sonuçları `projects/` altına commit'ler, insan gözden geçirir.

## Workflow'lar

| Dosya | Ne yapar | Nasıl tetiklenir |
|---|---|---|
| `dispatch.yml` | Konuları tazeler (`batch_research.py`) ve 75+ puanlı nişleri kanallara dağıtır (`dispatcher.py`) | Cron: Pzt/Prş 06:00 UTC + manuel (`dry_run`, `min_score` girdileriyle) |
| `youtube-research.yml` | Sabit/girilen konu listesini araştırır, hikâye DNA ve CEO kararı (V1) üretir | Manuel (`topics` girdisi) |
| `channel-health.yml` | Tek bir YouTube kanalının sağlığını analiz eder | Manuel (`channel` girdisi) |
| `competitor-health.yml` | Kendi kanalı rakiplerle karşılaştırır | Manuel (`own_channel`, `competitors`) |
| `video-dna.yml` | Tek bir videonun "DNA"sını (yapı, tempo) çıkarır | Manuel (`video_url`) |
| `decision-v2.yml` | Sadece CEO karar motorunu (V2) tek başına çalıştırır | Manuel |
| `run-shp.yml` | Yukarıdaki "PRO akış"ın tamamını uçtan uca çalıştırır (Script Agent V2 dahil) | Manuel (`own_channel`, `competitors`, `video_url`) |

Hepsinde `permissions: contents: write` var (üretilen raporları `projects/` altına commit'leyebilmek için).

## Gerekli secret'lar

Değerler burada **asla** yazılmaz — sadece isim ve amaç. Repo → Settings → Secrets and variables → Actions.

| Secret | Ne işe yarar | Hangi workflow(lar) |
|---|---|---|
| `YOUTUBE_API_KEY` | YouTube Data API v3 — niş araştırması, kanal/rakip/video analizi | dispatch, youtube-research, channel-health, competitor-health, video-dna, run-shp |
| `CROSS_REPO_TOKEN` | `repo` yetkili GitHub PAT — `dispatcher.py`'nin kanal repolarına `repository_dispatch` gönderebilmesi için | dispatch |
| `GROQ_API_KEY` | Ücretsiz Groq modeli — Script Agent V2'nin script/storyboard üretimi | run-shp |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Workflow başarısız olunca Telegram'a bildirim | dispatch (yoksa adım sessizce atlanır) |

## Manuel çalıştırma

GitHub'da **Actions** sekmesi → soldan ilgili workflow'u seç → **Run workflow** → gerekiyorsa girdileri doldur → çalıştır.

> **Not:** "Re-run" (eski bir çalışmayı tekrar çalıştır) her zaman o an `main` branch'inde olan kodu çalıştırır, çalıştığı tarihteki kodu değil.

`dispatch.yml`'i test ederken `dry_run: true` seçersen `dispatcher.py` gerçek bir `repository_dispatch` göndermez, sadece ne göndereceğini loglar — kanalları tetiklemeden güvenle deneyebilirsin.

## Bilinen notlar / sorunlar

- **İki ayrı niş-araştırma sistemi var** ve birbirinden habersiz çalışıyor: basit akış (`batch_research.py`/`commander.py`, sabit 5 konu) ve PRO akış (`niche_intelligence.py`, kendi kanal verisinden dinamik konu üretir). İkisi de aynı `analysis.json` şemasını üretir ama farklı kod yollarından geçer — birleştirilmeleri ayrı bir görev (bkz. PR'daki Öneriler).
- `decision_engine.py` (V1) sadece `youtube-research.yml`'de kullanılıyor; asıl kullanılan `decision_engine_v2.py` (`decision-v2.yml`, `run-shp.yml`).
- `script_agent.py` (V1) artık hiçbir workflow tarafından çağrılmıyor — yerini `script_agent_v2.py`/`script_agent_v2/` paketi aldı, V1 geriye dönük uyumluluk için repoda duruyor.
- `dispatcher.py`'nin gerçekten bir kanalı tetiklediği bu oturumda doğrulanamadı — `CROSS_REPO_TOKEN`'ın var olup olmadığını ve doğru izne sahip olup olmadığını GitHub Actions secret listesinden göremiyoruz (değerler görünmez); sadece `dry_run` modunda test edildi.
- `docs/`, `*_bible.md`, `producer_prompt.md`, `shp_core.md` gibi dosyalar kod değil, referans/prompt dokümanlarıdır (marka sesi, üretim kuralları) — script'ler tarafından otomatik okunmaz.
