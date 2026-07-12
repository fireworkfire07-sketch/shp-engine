# SHP Decision Log

## 2026-07-11 — Fixed SHP identity

Decision: SHP remains the CEO and decision engine.

Reason: The project repeatedly drifted between niche finder, video generator, SEO tool and publisher. This caused confusion and loss of trust.

Permanent rule: SHP analyzes, compares, decides, assigns and reviews. Specialist agents produce, edit, publish or design.

## 2026-07-11 — Preserve working features

Decision: New capabilities are additive modules. Existing working features must not be removed or silently repurposed.

## 2026-07-11 — Truthful status reporting

Decision: Never report a commit, test or integration as complete unless it has actually been performed and verified.

## 2026-07-11 — Communication mode

Decision: Use short, specific, action-first responses. Avoid long roadmaps unless explicitly requested.

## 2026-07-11 — YouTube optimization experiment

Decision: Two existing videos were repackaged. Their internal video content will not be changed until analytics data is reviewed.

## 2026-07-12 — Script Agent V2 (Head Writer AI pipeline)

Decision: Script Agent was upgraded to a modular V2 pipeline (`script_agent_v2/`) of independent engines — Knowledge, Story DNA, Psychology, Audience, Curiosity, Retention, Emotion, Originality, Visual Thinking, Fact, Script Generator, Script Doctor, Memory, CEO Reviewer — that rejects and rewrites its own script drafts when they don't clear a CEO quality gate, instead of only producing one pass.

Reason: Script quality is SHP's highest-priority output. A single-pass generator with a rule-based fallback could not self-evaluate curiosity, retention risk, emotional pacing, originality risk or unverified claims, or reject its own weak output.

Permanent rule (per SHP Constitution's additive-module rule): `script_agent.py` (V1) is untouched and still runnable directly. `run-shp.yml` now calls `script_agent_v2.py`; CI validates output structure but does not fail the build on a CEO REJECT — a rejected script with honest reasons is a valid, truthful pipeline output, not a failure.
