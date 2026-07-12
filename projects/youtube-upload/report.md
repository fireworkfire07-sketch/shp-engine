# SHP YouTube Upload Raporu

**Durum:** DRY_RUN_VALIDATION_FAILED
**Mod:** DRY_RUN
**Gizlilik:** private
**Video ID:** -
**Video URL:** -

## Gerekçe / durum notları

- Video CEO Pro kararı: DUR.
- Gerçek API çağrısı yapılmadı (DRY_RUN).

## Doğrulama hataları

- Final video dosyası bulunamadı: None
- Thumbnail görseli bulunamadı: None

## Gerçek sınırlar

- privacyStatus PRIVATE_UPLOAD/DRY_RUN/PREPARE_UPLOAD için her zaman 'private' olarak zorlanır.
- PUBLIC_UPLOAD varsayılan olarak kapalıdır; yalnızca YOUTUBE_ALLOW_PUBLIC=true açıkça ayarlanırsa denenir.
- Bu depoda gerçek bir YouTube OAuth hesabına karşı canlı test yapılmamıştır (kimlik bilgisi yok); istek inşası API sözleşmesine göredir ve mock transport ile test edilmiştir — canlı ilk kullanım öncesi kimlik bilgili bir manuel duman testi gerekir.
