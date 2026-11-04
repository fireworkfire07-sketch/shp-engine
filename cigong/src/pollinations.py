"""Pollinations.ai uzerinden ucretsiz, API-key'siz gorsel uretimi.

Sabit SEED + sabit CHARACTER_DESC (bkz. config/phase_metal.py) = tutarli
figur. Higgsfield Element gibi ucretli bir karakter-tutarliligi servisinin
ucretsiz karsiligi budur; mukemmel degil ama ink-wash soyutlamasinda
sapmalar goze batmiyor (bkz. README -> "Tutarlilik notu").
"""

from __future__ import annotations

import pathlib
import time
import urllib.parse

import requests

BASE_URL = "https://image.pollinations.ai/prompt/{prompt}"
DEFAULT_MODEL = "flux"
MIN_VALID_BYTES = 5000


def gen(prompt: str, out_path: str | pathlib.Path, seed: int, w: int = 1280, h: int = 720,
        model: str = DEFAULT_MODEL, attempts: int = 5) -> pathlib.Path:
    """Tek bir gorsel uretir, out_path'e yazar, o path'i dondurur.

    Gercek bir HTTP hatasi veya suphesiz-kucuk bir cevapta `attempts` kez
    yeniden dener (SHP kanal script'leriyle ayni desen). Son denemede de
    basarisizsa istisna firlatir — cagiran taraf (render.py) bunu nasil
    ele alacagina karar verir (ör. onceki gorseli tekrar kullanma).
    """
    out_path = pathlib.Path(out_path)
    url = BASE_URL.format(prompt=urllib.parse.quote(prompt))
    params = {"width": w, "height": h, "seed": seed, "model": model, "nologo": "true"}

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(url, params=params, timeout=180)
            if r.ok and len(r.content) >= MIN_VALID_BYTES:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(r.content)
                return out_path
            last_error = RuntimeError(f"kotu cevap: HTTP {r.status_code}, {len(r.content)} byte")
        except requests.RequestException as exc:
            last_error = exc
        print(f"  [pollinations] deneme {attempt}/{attempts} basarisiz: {last_error}", flush=True)
        if attempt < attempts:
            time.sleep(10 * attempt)

    raise RuntimeError(f"Pollinations gorseli uretilemedi ({attempts} deneme): {last_error}")
