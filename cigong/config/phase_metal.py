"""Metal evresi sabitleri: karakter kimligi, gorsel stil, zamanlama.

Bu dosya SADECE veri/konfigurasyon icerir. Baska bir evre (Su, Agac, Ates,
Toprak) eklerken bu dosyanin bir kopyasi alinir; sadece SEED, CHARACTER_DESC
(gerekirse), ve asagidaki palet/duruş degerleri degisir — render.py/assemble.py
motoru aynen kalir (bkz. cigong/README.md -> "Olcekleme").
"""

# Bu bolumun karakter seed'i — TUM planlarda ayni kalacak (tutarlilik icin).
SEED = 74721

CHARACTER_DESC = (
    "a calm androgynous young practitioner, serene face, eyes gently closed, "
    "simple flowing linen practice robe with loose sleeves and a soft waist sash, "
    "hair in a simple low knot, barefoot"
)

STYLE = (
    "traditional sumi-e ink-wash painting, monochrome black ink with soft grey "
    "wash gradients on warm cream rice paper, minimal confident brushstrokes, "
    "expressive empty negative space, delicate ink bleed, no text, no color, "
    "meditative Taoist atmosphere"
)

# Metal paleti: figurun "rengi" bir ton degil — kagidin beyazinin canlanmasi.
BRIGHTEN_AT = 10  # kacinci planda beyaz "canlanacak" (donusum, 1-indeksli)

W, H, FPS = 1280, 720, 25

PHASE_NAME = "metal"
POEM_FILE = "assets/poem_metal.txt"
OUTPUT_NAME = "metal_pilot.mp4"
