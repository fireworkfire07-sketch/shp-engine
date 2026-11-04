#!/usr/bin/env python3
"""Cigong pilotu ana orkestrasyon: config/phase_metal.py + config/shots.py'yi
okur, her plani render eder (src/render.py), birlestirir ve muzigi bindirir
(src/assemble.py) -> out/metal_pilot.mp4.

Kullanim:
  python3 run_pilot.py                 # gercek Pollinations gorselleri (ag gerekir)
  CIGONG_OFFLINE=1 python3 run_pilot.py  # yer-tutucu gorsellerle kuru calistirma
                                          # (ffmpeg/montaj mekanigini test eder,
                                          # GERCEK SANAT URETMEZ)
"""

from __future__ import annotations

import os
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "config"))

import render  # noqa: E402
import assemble  # noqa: E402
import phase_metal as phase  # noqa: E402
from shots import iter_shots  # noqa: E402


def main() -> None:
    offline = os.environ.get("CIGONG_OFFLINE", "").strip().lower() in {"1", "true", "yes"}
    if offline:
        print("CIGONG_OFFLINE=1: yer-tutucu gorsellerle KURU calistirma (gercek sanat yok).", flush=True)

    work_dir = ROOT / "work"
    out_dir = ROOT / "out" / "plans"
    final_dir = ROOT / "out"
    work_dir.mkdir(exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(exist_ok=True)

    shot_clips = []
    for shot in iter_shots():
        print(f"Plan {shot['id']:02d}/12 ({shot['sec']}s, {shot['motion']}) render ediliyor...", flush=True)
        clip = render.render_shot(shot, phase, work_dir, out_dir, offline=offline)
        shot_clips.append((shot, clip))
        print(f"  -> {clip}", flush=True)

    print("Planlar birlestiriliyor...", flush=True)
    silent = final_dir / "silent.mp4"
    assemble.assemble_silent(shot_clips, work_dir, silent)

    music_path = ROOT / "assets" / "audio" / "metal_bed.mp3"
    final_out = final_dir / phase.OUTPUT_NAME
    print("Muzik bindiriliyor (varsa)...", flush=True)
    assemble.mux_music(silent, music_path if music_path.exists() else None, final_out)

    print(f"\nTamam: {final_out}")


if __name__ == "__main__":
    main()
