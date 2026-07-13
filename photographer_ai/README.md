# Photographer AI

A batch RAW/JPEG culling and editing pipeline: point it at a folder of
photos, get back quality-scored, star-ranked, edited, cropped and exported
images with a JSON report.

```
pip install -r photographer_ai/requirements.txt
python -m photographer_ai.cli run /path/to/photos --output ./out
```

See `models.py` for the `ImageRecord` data model threaded through every
stage, and `pipeline.py` for how the 13 spec stages are sequenced.

## What's real vs. what's a documented stub

The master spec (13 stages, GPU pipeline, full studio UI, generative eye
restoration, semantic object removal, learned aesthetic scoring) describes
a multi-month team effort. This implementation prioritizes **honesty over
appearing complete**: every stage below either does real, verifiable work
on real images, or is a clearly-marked interface waiting for a model this
sandboxed environment doesn't have.

| Stage | Status | How |
|---|---|---|
| 1. Quality Analysis | **Real** | Laplacian-variance sharpness, exposure histogram, Immerkaer noise estimate, gray-world color cast, perceptual-hash duplicate/burst detection |
| 2. Face Engine | **Real (classical CV)** | OpenCV Haar cascades for face + eye detection/open-closed. Emotion, gaze angle, skin quality: documented gap. Eye restoration: stub that always defers to manual review, per the spec's "never fake eyes" rule |
| 3. Body Analysis | **Real, network-dependent** | MediaPipe BlazePose (33 keypoints), lazily downloaded and cached. Gives posture tilt, symmetry, cropped-limb detection. Finger-level detail: documented gap. Degrades gracefully (`implemented=False`) if the model can't be fetched or native libs are missing |
| 4. Composition Engine | **Real (heuristic)** | Rule-of-thirds via subject-point distance, edge-energy entropy for framing/balance, sharpness-ratio subject isolation |
| 5. Background Cleanup | **Real detection, conservative removal** | MediaPipe object detector flags COCO-class distractions (people, cars, bottles, bags...); only auto-removes small isolated ones via inpainting, flags larger ones instead of risking visible smearing. "Trash", power lines, reflections: not detectable without different techniques (documented gap) |
| 6. Lightroom AI | **Real** | White balance, exposure, highlight/shadow recovery, contrast, vibrance, conditional denoise/sharpen — each driven by the actual Stage 1 measurements, not applied blindly |
| 7. Crop Engine | **Real** | Aspect-ratio crops for every spec-listed platform, keeps detected faces fully in frame, positions subject at the upper third |
| 8. Portrait Retouch | **Real, bounded** | Morphological blemish-spot detection + inpainting, restricted to face boxes and small spots only — pores/texture elsewhere untouched |
| 9. Hero Shot Detector | **Real (measurable half)** | Weighted combination of Stages 1/2/4. "Storytelling"/"impact" need scene semantics: documented gap, not faked with a placeholder score |
| 10. Black & White Engine | **Real** | Red-weighted channel mix (film-filter style) + S-curve + optional grain — not a naive desaturate |
| 11. Cinematic Shadow Compositor | **Real (classical primitives)** | CLAHE local contrast + radial dodge/burn centered on the subject. Matching a specific film-stock/LUT look: documented gap |
| 12. Export | **Real** | high-res / web / preview / watermarked-preview / per-platform crops / B&W-for-hero / ZIP bundle |
| 13. Photo Ranking | **Real** | ★1–★5 from the Stage 9 hero score, with bucket filtering |

No GPU pipeline, resumable job queue, or studio UI is implemented -
`pipeline.py` runs single-threaded and is explicitly documented as
trivially parallelizable (each stage is a pure per-image function) rather
than built out further in this pass.

## Dependencies

Core: `numpy`, `Pillow`, `opencv-python-headless` (pinned `<5` — v5 dropped
the bundled Haar cascade data files this pipeline relies on for face/eye
detection), `imagehash`, `rawpy` (RAW decoding via bundled libraw),
`pillow-heif` (HEIC/HEIF).

Optional, for Stage 3 / Stage 5: `mediapipe`. Needs network access on
first run (downloads ~6MB and ~4.5MB model files from Google's public
MediaPipe model store, cached under `~/.cache/photographer_ai/models/`)
and the system libraries `libgles2` / `libegl1` / `libegl-mesa0`
(`apt-get install -y libgles2 libegl1 libegl-mesa0` on Debian/Ubuntu).
Both stages degrade gracefully and report `implemented=False` instead of
crashing the batch if either prerequisite is missing.

## Tests

```
python -m unittest photographer_ai.tests.test_stages -v
```

Runs fully offline (Stage 3/5 are disabled in the integration test via
`PipelineConfig` flags to avoid a hard network dependency in CI).
