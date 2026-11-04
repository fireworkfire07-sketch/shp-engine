"""Metal evresinin 12 planlik senaryosu (sahne verisi, kod degil).

Her plan: (id, sec, scene, figure, motion, overlay[, note])
  id      : plan sira no (1-12)
  sec     : plan suresi (saniye)
  scene   : Pollinations prompt govdesi (Ingilizce, sahne tarifi)
  figure  : bu planda CHARACTER_DESC prompt'a eklensin mi (bool)
  motion  : render.py'nin taniyacagi hareket reçetesi (bkz. render.py MOTIONS)
  overlay : siir fragmani (Turkce, ekrana kaligrafi olarak binecek) veya None
  note    : opsiyonel serbest not (bu senaryoda hic kullanilmadi, geriye donuk
            uyumluluk icin destekleniyor)

Pollinations prompt'u render.py'de su sekilde kurulur:
  prompt = f"{CHARACTER_DESC + ', ' if figure else ''}{scene}, {STYLE}"
"""

SHOTS = [
    (1, 12, "empty warm cream rice paper, a single dry autumn leaf drifting down, vast negative space", False, "push_in_slow", None),
    (2, 14, "wide misty valley, a single bare tree silhouette, pale light from the west, a few leaves suspended in air", False, "push_in_slow", None),
    (3, 16, "seen from behind at the foot of a bare tree, shoulders slightly slumped, leaves falling one by one around", True, "hold", None),
    (4, 13, "montage of contraction: a curling drying leaf / a shrinking bare tree / a figure folding inward", True, "cut_montage", None),
    (5, 13, "the figure slowly straightens, back upright, feet shoulder-width, knees softly bent, calm", True, "push_in_slow", None),
    (6, 17, "the figure raising both arms, embracing a large invisible ball at chest height, elbows lower than wrists, faint glow gathering between the arms", True, "hold", None),
    (7, 20, "close on hands and chest, the ball of light gently expanding, pushing the arms slightly outward", True, "push_in_slow", None),
    (8, 20, "close on hands, the ball shrinking, palms feeling resistance", True, "hold", "Ben nefes aldım —\nsenin, ağacın, denizin, kedinin\nnefesi bana karıştı"),
    (9, 17, "wide, the figure in the stance, thin ink lines reaching from the figure to the tree, the mist, a distant bird, connecting them", True, "crossfade_from_prev", "Nefes nefese hamileyiz birbirimize,\nayrıymış gibi yapıyoruz"),
    (10, 13, "the figure luminous, edges sharpened, standing in bright clear frost-white autumn air, serene", True, "brighten", None),
    (11, 15, "a last leaf falling and turning into a seed as it lands, the figure still in the stance, peaceful", True, "hold", None),
    (12, 10, "empty luminous cream paper, full living stillness", False, "brighten_to_white", "Hayat akar nefeste."),
]

SHOT_FIELDS = ("id", "sec", "scene", "figure", "motion", "overlay", "note")


def iter_shots():
    """SHOTS'taki her tuple'i (6 veya 7 eleman) sabit alanli bir dict'e cevirir."""
    for row in SHOTS:
        values = list(row) + [None] * (len(SHOT_FIELDS) - len(row))
        yield dict(zip(SHOT_FIELDS, values))
