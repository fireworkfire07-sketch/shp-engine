Bu klasor bos commit'lenemiyor (git bos dizin takip etmez), bu .gitkeep onun icin.

GEREKEN: Caveat-Regular.ttf (Turkce destekler, fonts.google.com/specimen/Caveat).
Bu dosya buraya eklenmeden calligraphy.py otomatik olarak sistemdeki
DejaVuSans-Bold'a duser (Turkce'yi tam destekler ama firca hissi vermez) ve
bunu acikca loglar — pipeline durmaz.

.github/workflows/cigong_pilot.yml, calismasi sirasinda Google Fonts
GitHub mirror'indan Caveat'i indirmeyi DENER (gercek sanal makinenin internet
erisimi var); basarisiz olursa ayni sekilde DejaVuSans'a duser.
