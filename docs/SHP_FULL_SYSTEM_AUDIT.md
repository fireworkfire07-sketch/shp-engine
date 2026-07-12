# SHP Full System Audit

Evidence-based, file-by-file. Every claim below was verified by reading the
actual source in this repository (commit `ac85ae5` / branch
`claude/blissful-planck-l193kc`) — nothing here is inferred from filenames
or docs alone.

Status legend:
- **WORKING AND INTEGRATED** — real logic, real output, wired into the run-shp.yml master chain, and affects a downstream decision.
- **WORKING BUT NOT INTEGRATED** — real logic and output exist, but the module is not part of the current master chain (legacy/standalone path).
- **PARTIALLY IMPLEMENTED** — real logic exists but the deliverable is incomplete against the target spec (missing fields, missing modality, etc.).
- **REFERENCED BUT NOT FUNCTIONAL** — the concept/name appears in code or docs but no module actually performs the described behavior.
- **PLACEHOLDER** — exists only as a name/stub with no real logic.
- **MISSING** — no file, no code, nothing.
- **BROKEN** — code exists but fails or produces incorrect output.

---

## Summary table

| # | Capability | Status | Files | Real Input | Real Output | Test | Connected to Workflow | Affects Decision |
|---|---|---|---|---|---|---|---|---|
| 1 | Channel Analyzer | WORKING AND INTEGRATED | `channel_analyzer.py` | YouTube Data API v3 (live HTTP) | `projects/channel-health/{analysis.json,report.md}` | None | `run-shp.yml` step "Kanalı analiz et" | Feeds Decision Engine's `channel_health_score`, `channel_identity` |
| 2 | Competitor Analyzer | WORKING AND INTEGRATED | `competitor_analyzer.py` (reuses `channel_analyzer.py` functions) | YouTube Data API v3 (live HTTP) | `projects/competitor-health/{analysis.json,report.md}` | None | `run-shp.yml` step "Rakipleri analiz et" | Feeds Decision Engine's `competitor_reference`, `rival_proof_score` |
| 3 | Niche Intelligence | WORKING AND INTEGRATED | `niche_intelligence.py` | YouTube Data API v3, scans 40 query candidates × 3 time windows | `projects/niche-intelligence/{analysis.json,report.md}`, `projects/batch-ranking.{json,md}` | None | `run-shp.yml` steps "PRO niş keşfi" + "PRO niş verisini karar motoruna aktar" | Sets the `winner` niche that Decision Engine selects the topic from |
| 3b | Niche Intelligence (legacy V1) | WORKING BUT NOT INTEGRATED | `batch_research.py`, `commander.py`, `decision_engine.py` | YouTube Data API v3 | `projects/<slug>/{analysis.json,report.md}`, `projects/decision-report.*` | None | Only `youtube-research.yml` (separate, non-master workflow) | None on the master chain — superseded by #3, #6 |
| 4 | Story DNA | WORKING AND INTEGRATED | `story_report.py`, `story_score.py` | Reads every `projects/*/analysis.json` video title already fetched by #1–#3 | `projects/story-dna.{md,json}` | None | `run-shp.yml` step "Hikâye DNA puanlarını çıkar" | Consumed by Script Agent V2's `ProductionContext.story_dna` and by `story_dna_engine.py` |
| 5 | Video DNA | WORKING AND INTEGRATED (conditional) | `video_dna.py` | YouTube Data API v3 + optional `youtube-transcript-api` transcript | `projects/video-dna/<id>/{analysis.json,report.md,transcript.json}` | None | `run-shp.yml` step "İsteğe bağlı video DNA analizi", gated on `inputs.video_url != ''` | Feeds `originality_engine.plan()` avoid-corpus and `knowledge_engine` fallback lead when present; **skipped entirely on most runs** since it requires an explicit `video_url` input |
| 6 | Decision Engine | WORKING AND INTEGRATED | `decision_engine_v2.py` | `channel-health`, `competitor-health`, `batch-ranking` JSON | `projects/ceo-decision/{analysis.json,report.md}` — decision ÇEK/TEST ET/BEKLET, `video_idea`, `channel_fit_score` | None | `run-shp.yml` step "CEO kararını üret" | Selects the topic and video idea that everything downstream (Script Agent V2) writes about |
| 7 | Effort / Return Filter | WORKING AND INTEGRATED | `effort_filter.py` | `ceo-decision`, `channel-health`, `competitor-health`, `batch-ranking` JSON | Mutates `projects/ceo-decision/analysis.json` in place with `effort_verdict`/`effort_value_score`/`effort_action`; appends section to `report.md` | None | `run-shp.yml` step "Emek ve beklenen getiriyi hesapla" | Can downgrade ÇEK→TEST ET or force DUR; gates final validation in `run-shp.yml` |
| 8 | Growth Advisor | WORKING AND INTEGRATED | `growth_advisor.py` | `channel-health`, `competitor-health`, `ceo-decision` JSON | `projects/growth-advisor/{analysis.json,report.md}` — hook, retention plan, publish time, hashtags | None | `run-shp.yml` step "Keşfet ve büyüme planını üret" | Feeds `ProductionContext` (`first_3_seconds`, `retention_plan`, `hashtags`, `keywords`) directly into Script Agent V2 |
| 9 | Script Agent V2 | WORKING AND INTEGRATED, gaps below | `script_agent_v2/` (14 engine modules + `pipeline.py`, `context.py`, `outputs.py`, `llm.py`, `textutil.py`), entrypoint `script_agent_v2.py` | Every JSON above via `context.build_context()`; GROQ API when `GROQ_API_KEY` set, deterministic fallback otherwise | 9 files in `projects/script-agent/`: `script.{md,json}`, `storyboard.json`, `visual_prompts.json`, `voiceover.txt`, `subtitle.srt`, `thumbnail.json`, `youtube_upload.json`, `video_engine_handoff.json`, `memory.json` | None | `run-shp.yml` step "Script Agent V2 — Head Writer AI pipeline" | APPROVE/REJECT gates `video_engine_handoff.status`; script content is real, GROQ-or-fallback generated narration, not a stub — **but see gaps** |
| 10 | Video CEO | REFERENCED BUT NOT FUNCTIONAL | none dedicated | — | — | — | not in workflow | Two *different, narrower* things currently answer to "CEO": `decision_engine_v2.py` (topic-selection ÇEK/TEST ET/BEKLET) and `script_agent_v2/engines/ceo_reviewer.py` (script-only APPROVE/REJECT on 6 weighted dimensions). **Neither reviews the finished production package** (thumbnail concept, SEO, monetization/policy risk, series potential, first 10s/30s) or returns ÇEK/DÜZELT/DUR/BEKLET as this task's Phase 2 requires. This is the largest gap in the system. |
| 11 | Video Engine | MISSING | — | — | — | — | — | No `video_engine.py`, no render manifest, no FFmpeg pipeline, no `projects/video-engine/` directory anywhere in the repo. |
| 12 | Voiceover | PARTIALLY IMPLEMENTED | `script_agent_v2/outputs.py::build_voiceover_txt` | Final approved/rejected script sections | `projects/script-agent/voiceover.txt` — narration **text** only | None | Part of Script Agent V2 step | No TTS, no audio file, no adapter pattern, no timing manifest beyond the SRT estimate. It is a script for a narrator to read, not a voiceover system. |
| 13 | Subtitle generation | WORKING AND INTEGRATED | `script_agent_v2/outputs.py::build_subtitle_srt`, `textutil.estimate_seconds` | Script sections | `projects/script-agent/subtitle.srt` — real numbered SRT cues with computed timestamps | None | Part of Script Agent V2 step | Referenced by `video_engine_handoff.json.subtitle_file` and `youtube_upload.json.captions_file`. Real limitation (already disclosed in code/report): timing is estimated from reading speed, not measured from actual audio, because no audio exists yet. |
| 14 | Thumbnail generation package | PARTIALLY IMPLEMENTED | `script_agent_v2/outputs.py::build_thumbnail` | Script title + `thumbnail_direction` + originality eval | `projects/script-agent/thumbnail.json` — concept text, text-overlay suggestion, style notes, originality-risk flag | None | Part of Script Agent V2 step | It is a **spec for a thumbnail**, not an image. No image generation or asset file. |
| 15 | YouTube metadata package | WORKING AND INTEGRATED | `script_agent_v2/outputs.py::build_youtube_upload` | Script title/description/tags, `ceo_review` | `projects/script-agent/youtube_upload.json` — title, description, tags, hashtags, category, language, `"visibility": "private"`, `ceo_approved` flag | None | Part of Script Agent V2 step | Correctly defaults to private and gates `ceo_approved` on the script CEO decision. Nothing consumes it yet (see #16). |
| 16 | YouTube uploader | MISSING | — | — | — | — | — | No `youtube_uploader.py`, no OAuth flow, no upload API call, no DRY_RUN/PREPARE_UPLOAD/PRIVATE_UPLOAD modes anywhere. |
| 17 | Learning Engine | PARTIALLY IMPLEMENTED | `script_agent_v2/engines/memory_engine.py` | `projects/script-agent/memory.json` (own script run history) | Updated `memory.json`; `hints_for_generation()` output is injected into the next Script Generator prompt as `memory_hints` | None | Runs every Script Agent V2 invocation | Real and genuinely integrated for **structural self-learning** (hook length/shape patterns, ending patterns, average CEO score, pacing) — never stores literal wording. **But it never reads real published-video analytics** (views, likes, comments from #1/#2) — there is no code path from channel/competitor performance data back into niche selection or script generation. No `projects/learning-engine/` exists. |
| 18 | Workflow orchestration | PARTIALLY IMPLEMENTED | `.github/workflows/run-shp.yml` | — | — | Shell assertions (`test -f ...`) + a Python validation block at the end | Is the workflow | Correctly chains steps 1–9 above in order with real data dependencies and stops the build on structural failure (missing required JSON keys) while explicitly *not* failing on a CEO REJECT (see lines 211–214, a documented, deliberate design decision). It stops **before** Video CEO Pro, production-package completion, Video Engine, voiceover audio, uploader, learning engine, or a final-run report — i.e. it implements roughly the first 9 of the 12 target-architecture stages. Four additional legacy/standalone workflows exist (`channel-health.yml`, `competitor-health.yml`, `decision-v2.yml`, `video-dna.yml`) that duplicate individual steps outside the master chain, plus one fully-legacy V1 workflow (`youtube-research.yml` → `batch_research.py` + `decision_engine.py` V1). All five still run correctly; none are broken; none are part of the target chain. |
| 19 | Artifact handling | PARTIALLY IMPLEMENTED | `run-shp.yml` step "Script Agent V2 çıktılarını artifact olarak yükle" (added in PR #3, commit `c7a1e75`) | — | GitHub Actions artifact `script-agent-v2-outputs` containing `projects/script-agent/` | None | `run-shp.yml`, `if: always()` | Only one stage's outputs are captured as an artifact. The other 6 stages (channel/competitor/niche/decision/effort/growth) rely solely on the final git-commit step; if that step's `git push` ever fails (e.g. a non-fast-forward race), those reports are unrecoverable from the Actions UI. |
| 20 | Secrets and configuration | WORKING AND INTEGRATED, with a gap | `YOUTUBE_API_KEY`, `GROQ_API_KEY`, `GROQ_MODEL` referenced via `os.getenv`/`${{ secrets.* }}` throughout | — | — | — | Every workflow | YouTube-dependent modules hard-fail with a clear Turkish error when the key is missing (correct — there is no honest fallback for real YouTube data). Every Script Agent V2 engine has an explicit, labeled `rule_based_fallback` path when `GROQ_API_KEY` is absent (verified in `knowledge_engine.py`, `generator.py`, `doctor.py`, `originality_engine.py`, `visual_engine.py`). **Gap:** there is no `requirements.txt`/`pyproject.toml` anywhere in the repo — `youtube-transcript-api` is `pip install`-ed unpinned, ad hoc, in two separate workflow files. |
| 21 | Tests | MISSING | — | — | — | — | — | Zero `test_*.py` files, no `tests/` directory, no pytest config, no test job in any workflow. `test_commander.md` is a 12-line manual test note, not an automated test. |
| 22 | Failure recovery | MISSING | — | — | — | — | — | Every module hard-fails via `raise SystemExit` on bad input; the workflow has no distinct SYSTEM_SUCCESS/QUALITY_REJECT/BLOCKED_MISSING_DATA/TECHNICAL_FAILURE states, no per-stage diagnostic artifact capture beyond #19, and no documented recovery instruction on failure. |
| 23 | Production safety | PARTIALLY IMPLEMENTED | `script_agent_v2/outputs.py::build_youtube_upload` | — | `youtube_upload.json.visibility == "private"` by default | None | Part of Script Agent V2 step | The metadata correctly defaults private, but since #16 (uploader) doesn't exist, this guarantee is currently only a JSON field nobody reads — it is not yet an enforced safety mechanism. |

---

## Architecture note (read before Phase 2–7 implementation)

`docs/SHP_CONSTITUTION.md` states SHP itself "does not: generate or edit the
final video, draw the thumbnail, produce voiceover, upload content." That
rule is about the **SHP decision-engine identity**, not a ban on the system
having those capabilities — the same document's very next section says "new
capabilities are added as modules or agents." Script Agent V2 is already
exactly that pattern: a separate specialist module SHP's decision chain
hands work to. Video CEO, Video Engine, Voiceover, YouTube Uploader, and
Learning Engine should be built the same way — new specialist modules
downstream of SHP's decision, not changes to SHP's own decision logic. No
constitutional conflict; flagging this only so the distinction is explicit
before Phase 2–7 work begins.

## Gap list driving Phase 1–8 implementation

1. **Script Agent V2 approval threshold is 68/100, task requires 85/100** (`ceo_reviewer.py:16`). Raising it without also strengthening the generator/doctor will simply increase REJECT rate — both need to move together.
2. **Video CEO Pro does not exist** as a distinct production-package-level reviewer with ÇEK/DÜZELT/DUR/BEKLET decisions and a DÜZELT→rewrite loop back into Script Agent V2.
3. **Production package is missing required per-scene fields**: no explicit scene number, no `video_prompts.json` (separate from `visual_prompts.json`), no transition/music-direction/sound-effect-direction/emotional-purpose/curiosity-purpose per scene, and narration text lives only in `script.json`/`voiceover.txt`, not attached to each storyboard scene.
4. **No Video Engine** (lightweight FFmpeg mode or generative adapter).
5. **No real voiceover audio** (TTS adapter layer).
6. **No YouTube uploader** (any mode — DRY_RUN through PRIVATE_UPLOAD).
7. **Learning Engine doesn't close the loop on real analytics** (views/likes/comments back into niche/script decisions).
8. **No automated tests anywhere.**
9. **No failure-recovery / status taxonomy in the master workflow.**
10. **No final-run report** (`projects/final-run/`).

This audit is the required gate before implementation. Phase 1 work begins next.
