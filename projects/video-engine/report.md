# SHP Video Engine Raporu

**Durum:** STOPPED_BY_VIDEO_CEO
**Mod:** LIGHTWEIGHT_MODE
**Çözünürlük:** 1920x1080 @ 25fps
**Toplam süre:** 0 sn
**Final video:** üretilmedi
**Arka plan müziği:** yok (assets/audio/background_music.mp3|wav sağlanmadı)

## Gerekçe / durum notları

- Video CEO Pro kararı 'DUR'; üretim güvenli şekilde durduruldu, render denenmedi.

## Gerçek sınırlar

- Görsel API anahtarı yoksa sahne görselleri gerçek AI görseli değil, tipografik yerleşim kartıdır (assets/images/scene_NN.png|jpg sağlanırsa onun yerine kullanılır).
- Sahne süresi, gerçek TTS ses süresi varsa ondan; yoksa tahmini konuşma süresinden alınır — konuşma asla kesilmez.
- GENERATIVE_VIDEO_MODE bu depoda bağlı değildir; sadece arayüz mevcuttur (GenerativeVideoAdapter).
- Bu rapor sahte bir video üretimini asla bildirmez: final_video.mp4 yalnızca gerçekten render edildiyse mevcuttur.
