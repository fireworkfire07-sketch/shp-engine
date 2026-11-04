"""Plan video'larini birlestirir (v1 concat + crossfade_from_prev icin xfade
seam'i) ve muzigi bindirir.

v1 (brief): tum plan.mp4'leri concat demuxer ile uc uca ekle (sert kesme).
Bu dosyada TEK bir incelik var: motion alani "crossfade_from_prev" olan
planlar (bu senaryoda sadece plan 9) bir onceki plandan sert kesmeyle degil
xfade ile baglanir — brief'in ozellikle istedigi tek yumusak geçiş budur;
geri kalan her sey hala v1 sert-kesme mantiginda.
"""

from __future__ import annotations

import pathlib
import subprocess

XFADE_DURATION = 0.8


def _run_ffmpeg(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def _probe_duration(path: pathlib.Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def _concat(clips: list[pathlib.Path], out: pathlib.Path, work: pathlib.Path) -> pathlib.Path:
    if len(clips) == 1:
        if clips[0] != out:
            import shutil

            shutil.copy(clips[0], out)
        return out
    list_file = work / f"{out.stem}_concat_list.txt"
    list_file.write_text("".join(f"file '{p.resolve()}'\n" for p in clips), encoding="utf-8")
    _run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out)])
    return out


def _xfade_join(a: pathlib.Path, b: pathlib.Path, out: pathlib.Path) -> pathlib.Path:
    offset = max(_probe_duration(a) - XFADE_DURATION, 0.1)
    filt = f"[0][1]xfade=transition=fade:duration={XFADE_DURATION}:offset={offset},format=yuv420p"
    _run_ffmpeg(["-i", str(a), "-i", str(b), "-filter_complex", filt, str(out)])
    return out


def assemble_silent(shot_clips: list[tuple[dict, pathlib.Path]], work_dir: pathlib.Path, out_path: pathlib.Path) -> pathlib.Path:
    """shot_clips: [(shot_dict, clip_path), ...] sira ile. 'crossfade_from_prev'
    olarak isaretli bir plandan once xfade seam'i acilir, geri kalani concat."""
    work_dir.mkdir(parents=True, exist_ok=True)
    groups: list[list[pathlib.Path]] = [[]]
    for shot, clip in shot_clips:
        if shot["motion"] == "crossfade_from_prev" and groups[-1]:
            groups.append([])
        groups[-1].append(clip)

    group_outputs = []
    for i, group in enumerate(groups):
        group_out = work_dir / f"segment_{i:02d}.mp4"
        group_outputs.append(_concat(group, group_out, work_dir))

    if len(group_outputs) == 1:
        import shutil

        shutil.copy(group_outputs[0], out_path)
        return out_path

    joined = group_outputs[0]
    for i, nxt in enumerate(group_outputs[1:], start=1):
        step_out = work_dir / f"joined_{i:02d}.mp4"
        joined = _xfade_join(joined, nxt, step_out)
    import shutil

    shutil.copy(joined, out_path)
    return out_path


def mux_music(silent_video: pathlib.Path, music_path: pathlib.Path | None, out_path: pathlib.Path) -> pathlib.Path:
    """Muzik dosyasi yoksa (brief: 'senin koyacagin CC0 track') sessiz video
    oldugu gibi kopyalanir ve durum acikca loglanir — pipeline bu yuzden
    durmaz, ama cikti muziksiz olur."""
    if music_path is None or not pathlib.Path(music_path).exists():
        print(f"  [assemble] UYARI: muzik dosyasi yok ({music_path}) — cikti SESSIZ kalacak", flush=True)
        import shutil

        shutil.copy(silent_video, out_path)
        return out_path

    _run_ffmpeg([
        "-i", str(silent_video), "-i", str(music_path),
        "-c:v", "copy", "-c:a", "aac", "-shortest", str(out_path),
    ])
    return out_path
