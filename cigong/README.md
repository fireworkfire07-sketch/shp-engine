# Çigong Pilotu — Metal (ink-wash, sessiz)

5 evreye (Metal, Su, Ağaç, Ateş, Toprak) dayalı bir Çigong/Tai Chi anime dizisinin ilk pilot bölümü. Bu bölüm **Metal**: ~3 dakikalık, tamamen sessiz (TTS yok), sumi-e ink-wash tarzında bir animasyon. Sıfır ücretli servis — Pollinations (görsel), edge-tts değil (bu bölümde ses yok), ffmpeg (hareket/montaj), Pillow (kaligrafi).

Bu modül `shp-engine` reposunun içinde bağımsız bir klasör (`cigong/`) olarak duruyor — dispatcher'a (`dispatcher.py`, `channels.json`) **dokunmuyor**, ayrı bir repo açma iznim olmadığı için buraya kuruldu (bkz. PR açıklaması).

## Nasıl çalışır

```
config/phase_metal.py + config/shots.py   (12 planlık senaryo, sabit SEED+karakter)
  → src/render.py    her plan için: Pollinations görsel(ler) → ffmpeg hareket reçetesi → plan_XX.mp4
      (şiir varsa: src/calligraphy.py ile Pillow'da PNG üretilir, ffmpeg overlay ile bindirilir)
  → src/assemble.py  planları birleştirir (v1: concat; plan 9'da tek bir xfade geçişi) → silent.mp4
      müzik varsa bindirir → out/metal_pilot.mp4
```

Çalıştırma:

```bash
cd cigong
pip install -r requirements.txt
python3 run_pilot.py                    # gerçek Pollinations görselleri (ağ gerekir)
CIGONG_OFFLINE=1 python3 run_pilot.py   # yer-tutucu görsellerle kuru çalıştırma
```

`CIGONG_OFFLINE=1`, Pollinations'a hiç gitmeden düz renkli yer-tutucu görseller kullanır — **gerçek sanat üretmez**, sadece ffmpeg/montaj mekaniğini (zoompan, cut_montage, xfade, brighten, kaligrafi overlay, müzik mux) test eder.

## Ağ erişimi — bu oturumda gerçekten test edemediğim kısım

Bu sandbox'ın ağ ilkesi `image.pollinations.ai` ve `fonts.google.com`'u engelliyor (gateway 403, politika reddi — doğrulandı, tahmin değil). Bu yüzden:
- **Gerçek Pollinations görselleriyle hiç test edemedim.** Yalnızca `CIGONG_OFFLINE=1` (yer-tutucu) modda uçtan uca çalıştırdım.
- **Caveat fontunu indiremedim.** `calligraphy.py` bu durumda otomatik olarak sistemdeki `DejaVuSans-Bold`'a düşüyor (Türkçe'yi tam destekler, fırça hissi vermez) ve bunu açıkça logluyor.
- GitHub Actions workflow'u (`cigong_pilot.yml`) hem Pollinations'a hem Google Fonts'a erişebilir (gerçek bir GitHub runner, bu sandbox'ın ağ kısıtı yok) — **gerçek ilk çalıştırma orada yapılmalı**, `workflow_dispatch` ile elle tetiklenir.

## Karşılaşılan ve düzeltilen bir bug

İlk yazımda şiir overlay'i (`src/render.py` → `_overlay_poem`) **görünmüyordu** — yer-tutucu testte metin tamamen şeffaf kalıyordu. Kök neden: `poem_png` girdisine `-loop 1` verilmemişti; ffmpeg PNG'yi tek, neredeyse sıfır süreli bir kare olarak okuyordu, `fade=in:d=1.5` o tek kareyi zamana yayamıyordu. `-loop 1` eklendi; bu da ikinci girdiyi sonsuz yaptığı için `-shortest` denendi (güvenilmez/çok yavaş bulundu — 467s'lik bozuk bir dosya üretti), onun yerine çıktıya açıkça `-t <plan_süresi>` verildi. Düzeltme sonrası 3 ayrı plan (8, 9, 12) için kareler çekilip görsel olarak doğrulandı.

## Tutarlılık notu (brief'ten, dürüst tekrar)

Sabit `SEED` + sabit `CHARACTER_DESC`, ink-wash soyutlaması sayesinde figürü "yeterince" tutarlı tutar; küçük sapmalar bu stilde göze batmaz. Daha güçlü tutarlılık için: önce tek bir referans kare üret/beğen, sonra Pollinations'ın `image=<url>` (img2img) parametresiyle diğer planları o referanstan türet — bu pilota eklenmedi, bir sonraki iyileştirme adımı.

## Yaptığım yorum gerektiren 2 karar

1. **`cut_montage` (plan 4) süre bölünmesi:** Brief "3 ayrı still, her biri ~1.4 sn" diyor ama plan 4'ün toplam süresi 13s — 3×1.4=4.2s, planın geri kalanını açıklamıyor. Toplam `sec` değerini (13s) 3 alt-görsele eşit böldüm (~4.3s/her biri) ki montajın toplam video süresine katkısı (brief'in "~3 dakika" hedefi) tutsun; bölme `round()` kullandığı için 13s yerine fiilen 12s çıkıyor (3×4s) — ~3 dakikalık toplamda önemsiz bir fark.
2. **`crossfade_from_prev` (plan 9):** Her planı bağımsız render edip (`render.py`), birleştirme aşamasında (`assemble.py`) SADECE bu plana giriş için sert kesme yerine xfade uyguladım — brief'in "v1 sert kesme, SADECE plan 9 yumuşak geçsin" ayrımına birebir uyuyor, geri kalan tüm planlar hâlâ v1 concat mantığında.

## Eksik asset'ler (brief'in kendi notu: "yoksa placeholder + README notu")

- `assets/fonts/` — Caveat-Regular.ttf yok (bkz. yukarıda, ağ engeli). `assets/fonts/README.txt`'e not düşüldü.
- `assets/audio/metal_bed.mp3` — CC0 müzik yok ("senin koyacağın", brief). `assets/audio/README.txt`'e not düşüldü. Yokken `assemble.py` sessiz bir video üretir, durmaz.
- `assets/poem_metal.txt` — şiirin TAMAMI elimde yok, sadece `shots.py`'deki 3 ekran fragmanı var. Başka dize UYDURMADIM.

## Ölçekleme (brief'ten)

Her şey `config/phase_*.py` + `config/shots.py` çiftine bağlı; `src/` motoru (pollinations/calligraphy/render/assemble) hiç değişmeden kalır. Yeni bir evre eklerken:
1. `config/phase_metal.py`'yi kopyala → `config/phase_<evre>.py`, `SEED`'i ve (gerekiyorsa) `CHARACTER_DESC`/`STYLE`'ı değiştir.
2. `config/shots.py`'yi kopyala → `config/shots_<evre>.py`, yeni senaryo+şiir fragmanlarını yaz.
3. `run_pilot.py`'ye hangi evreyi çalıştıracağını söyleyen küçük bir CLI argümanı eklenmeli (bu pilotta yok, tek evre sabit import ediyor — ikinci evre eklenince bu genişletilmeli).

Sıra (brief): Su (kış, siyah, böbrek) → Ağaç (ilkbahar, yeşil) → Toprak (sarı) → Ateş (en zoru, final).
