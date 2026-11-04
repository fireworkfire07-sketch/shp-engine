"""Siir fragmanlarini seffaf zeminli PNG'ye render eder (TTS yok, kaligrafi var).

Turkce glifleri (ç ğ ş ı ö ü İ) iceren bir firca/el yazisi fontu gerekir.
Varsayilan: assets/fonts/Caveat-Regular.ttf (Turkce destekler). CJK firca
fontlarinin cogunda Turkce yok, onlar KULLANILMAZ (bkz. brief notu).
Font dosyasi yoksa DejaVuSans-Bold'a (sistemde hazir, Turkce'yi tam
destekler ama firca hissi vermez) duser ve bunu acikca loglar.
"""

from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_CANDIDATES = [
    "assets/fonts/Caveat-Regular.ttf",
    "assets/fonts/Caveat-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

OPACITY = 229  # ~%90 (255 * 0.9)
BLUR_RADIUS = 1.2


def _resolve_font_path(font_path: str | None = None) -> tuple[str, bool]:
    candidates = ([font_path] if font_path else []) + FONT_CANDIDATES
    for candidate in candidates:
        if candidate and pathlib.Path(candidate).exists():
            return candidate, "dejavu" in candidate.lower()
    raise FileNotFoundError(
        "Hicbir kaligrafi fontu bulunamadi (assets/fonts/Caveat-Regular.ttf yok, "
        "sistem DejaVuSans-Bold da yok). En az biri gerekli."
    )


def render_poem_png(
    text: str,
    out_path: str | pathlib.Path,
    font_path: str | None = None,
    font_size: int = 64,
    max_width: int = 1100,
    color: tuple[int, int, int] = (255, 255, 255),
) -> pathlib.Path:
    """`text` (coklu satir olabilir) icin seffaf zeminli bir PNG uretir.

    Satirlar oldugu gibi korunur (siir kasitli satir kirmasi kullaniyor,
    kelime-kaydirma yapilmaz) ama her satir max_width'i asarsa font_size
    kademeli kucultulur.
    """
    out_path = pathlib.Path(out_path)
    lines = [ln for ln in text.split("\n") if ln.strip()] or [text]

    resolved_path, is_fallback = _resolve_font_path(font_path)
    if is_fallback:
        print("  [calligraphy] UYARI: Caveat fontu yok, DejaVuSans-Bold'a dusuldu (firca hissi olmayacak)", flush=True)

    measure_img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    measure_draw = ImageDraw.Draw(measure_img)

    size = font_size
    font = ImageFont.truetype(resolved_path, size)
    while size > 20:
        widest = max(measure_draw.textbbox((0, 0), ln, font=font)[2] for ln in lines)
        if widest <= max_width:
            break
        size -= 4
        font = ImageFont.truetype(resolved_path, size)

    line_height = int(size * 1.35)
    widest = max(measure_draw.textbbox((0, 0), ln, font=font)[2] for ln in lines)
    canvas = Image.new("RGBA", (widest + 40, line_height * len(lines) + 20), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    for i, ln in enumerate(lines):
        w = draw.textbbox((0, 0), ln, font=font)[2]
        x = (canvas.width - w) // 2
        y = 10 + i * line_height
        draw.text((x, y), ln, font=font, fill=(*color, OPACITY))

    if BLUR_RADIUS > 0:
        alpha = canvas.split()[3].filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
        canvas.putalpha(alpha)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "PNG")
    return out_path
