"""Her plan icin: still(ler) uret -> hareket reçetesini uygula -> plan_XX.mp4.

Hareket reçeteleri (brief Bolum 5):
  hold / push_in_slow : zoompan (zoom hizi farkli)
  cut_montage         : plan suresini N alt-goruntuye bolup sert kesmeyle birlestirir
  crossfade_from_prev : normal render edilir; assemble.py bu plani bir onceki
                         plandan xfade ile baglar (motion alani oradan okunur)
  brighten             : zamanla parlaklik rampasi
  brighten_to_white    : sona dogru beyaza sonme (karma DEGIL)
"""

from __future__ import annotations

import pathlib
import subprocess

import pollinations

PLACEHOLDER_COLOR = (235, 229, 214)  # sicak krem kagit tonu — ag erisimi yoksa yedek


def build_prompt(shot: dict, character_desc: str, style: str) -> str:
    prefix = f"{character_desc}, " if shot["figure"] else ""
    return f"{prefix}{shot['scene']}, {style}"


def _gen_or_placeholder(prompt: str, out_path: pathlib.Path, seed: int, w: int, h: int, offline: bool) -> pathlib.Path:
    """offline=True ise (ag erisimi yok / dry-run) Pollinations'a hic gitmeden
    sabit renkli bir yer-tutucu PNG uretir — render/assemble mekanigini test
    etmek icin, gercek sanat URETMEDEN. Bu GERCEK pipeline testi degildir,
    sadece ffmpeg/dosya-akisi dogrulamasidir (bkz. README -> Test notu)."""
    if offline:
        from PIL import Image

        out_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (w, h), PLACEHOLDER_COLOR).save(out_path)
        return out_path
    return pollinations.gen(prompt, out_path, seed=seed, w=w, h=h)


def _run_ffmpeg(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def _zoompan(img: pathlib.Path, out: pathlib.Path, sec: int, fps: int, w: int, h: int, zoom_per_frame: float) -> None:
    d = sec * fps
    vf = (
        f"scale={w*2}:{h*2},zoompan=z='min(zoom+{zoom_per_frame},1.15)':d={d}"
        f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}"
    )
    _run_ffmpeg(["-loop", "1", "-i", str(img), "-t", str(sec), "-vf", vf, "-pix_fmt", "yuv420p", str(out)])


def _cut_montage(scene: str, shot: dict, out: pathlib.Path, work: pathlib.Path, character_desc: str, style: str,
                  seed: int, w: int, h: int, fps: int, offline: bool) -> None:
    sub_scenes = [s.strip() for s in scene.split("/") if s.strip()]
    if not sub_scenes:
        sub_scenes = [scene]
    per_clip_sec = max(shot["sec"] / len(sub_scenes), 1.0)

    clip_paths = []
    for i, sub_scene in enumerate(sub_scenes):
        prompt = build_prompt({**shot, "scene": sub_scene}, character_desc, style)
        img = work / f"shot{shot['id']:02d}_sub{i}.png"
        _gen_or_placeholder(prompt, img, seed + i, w, h, offline)
        clip = work / f"shot{shot['id']:02d}_sub{i}.mp4"
        _zoompan(img, clip, round(per_clip_sec), fps, w, h, zoom_per_frame=0.0015)
        clip_paths.append(clip)

    list_file = work / f"shot{shot['id']:02d}_montage_list.txt"
    list_file.write_text("".join(f"file '{p.resolve()}'\n" for p in clip_paths), encoding="utf-8")
    _run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out)])


def _brighten(img: pathlib.Path, out: pathlib.Path, sec: int, fps: int, w: int, h: int) -> None:
    vf = (
        f"scale={w}:{h},zoompan=z='min(zoom+0.0006,1.1)':d={sec*fps}"
        f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},"
        f"eq=brightness='0.18*t/{sec}'"
    )
    _run_ffmpeg(["-loop", "1", "-i", str(img), "-t", str(sec), "-vf", vf, "-pix_fmt", "yuv420p", str(out)])


def _brighten_to_white(img: pathlib.Path, out: pathlib.Path, sec: int, fps: int, w: int, h: int) -> None:
    fade_dur = min(3, sec - 1)
    fade_start = sec - fade_dur
    vf = (
        f"scale={w}:{h},zoompan=z='min(zoom+0.0003,1.05)':d={sec*fps}"
        f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},"
        f"fade=t=out:st={fade_start}:d={fade_dur}:color=white"
    )
    _run_ffmpeg(["-loop", "1", "-i", str(img), "-t", str(sec), "-vf", vf, "-pix_fmt", "yuv420p", str(out)])


def _overlay_poem(video: pathlib.Path, poem_png: pathlib.Path, out: pathlib.Path, duration: float) -> None:
    # poem_png'ye -loop 1 ŞART: onsuz ffmpeg PNG'yi tek, neredeyse sifir-sureli
    # bir kare olarak okur; fade=in:d=1.5 o tek kareyi zamana yayamaz ve metin
    # pratikte hep (neredeyse) tam seffaf kalir — görünmez metin bugu buradan
    # geliyordu (bkz. cigong/README.md -> "Karsilasilan ve duzeltilen bir bug").
    # -loop 1 ayni zamanda ikinci girdiyi SONSUZ yapar, bu yuzden -shortest
    # yerine (guvenilmez/yavas bulundu) ciktiya acikca -t duration veriliyor.
    filt = "[1]format=rgba,fade=in:st=0:d=1.5:alpha=1[t];[0][t]overlay=(W-w)/2:(H-h)*0.78"
    _run_ffmpeg([
        "-i", str(video),
        "-loop", "1", "-i", str(poem_png),
        "-filter_complex", filt,
        "-t", str(duration),
        "-c:a", "copy",
        str(out),
    ])


def render_shot(shot: dict, phase, work_dir: pathlib.Path, out_dir: pathlib.Path, offline: bool = False) -> pathlib.Path:
    """Tek bir plani render eder, nihai plan_XX.mp4 yolunu dondurur (siir
    overlay'i varsa zaten bindirilmis olarak)."""
    work_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    shot_id = shot["id"]
    base = work_dir / f"shot{shot_id:02d}_base.mp4"

    if shot["motion"] == "cut_montage":
        _cut_montage(shot["scene"], shot, base, work_dir, phase.CHARACTER_DESC, phase.STYLE,
                     phase.SEED, phase.W, phase.H, phase.FPS, offline)
    else:
        prompt = build_prompt(shot, phase.CHARACTER_DESC, phase.STYLE)
        img = work_dir / f"shot{shot_id:02d}.png"
        _gen_or_placeholder(prompt, img, phase.SEED, phase.W, phase.H, offline)

        if shot["motion"] == "brighten":
            _brighten(img, base, shot["sec"], phase.FPS, phase.W, phase.H)
        elif shot["motion"] == "brighten_to_white":
            _brighten_to_white(img, base, shot["sec"], phase.FPS, phase.W, phase.H)
        elif shot["motion"] == "hold":
            _zoompan(img, base, shot["sec"], phase.FPS, phase.W, phase.H, zoom_per_frame=0.0001)
        else:  # push_in_slow, crossfade_from_prev -> ayni temel zoompan, bağlanti assemble.py'de
            _zoompan(img, base, shot["sec"], phase.FPS, phase.W, phase.H, zoom_per_frame=0.0004)

    final = out_dir / f"plan_{shot_id:02d}.mp4"
    if shot["overlay"]:
        from calligraphy import render_poem_png

        poem_png = work_dir / f"shot{shot_id:02d}_poem.png"
        render_poem_png(shot["overlay"], poem_png)
        _overlay_poem(base, poem_png, final, duration=shot["sec"])
    else:
        base.replace(final)

    return final
