"""Orchestrates the 14-stage Script Agent V2 pipeline:

Knowledge -> Story DNA -> Psychology -> Audience -> Curiosity -> Retention ->
Emotion -> Originality -> Visual Thinking -> Fact -> Script Generator ->
Script Doctor -> Memory -> CEO Reviewer.

Curiosity, Retention, Emotion, Originality and Fact each run twice: a
`plan()` stage before generation (setting targets) and an `evaluate()` stage
after Script Doctor (checking the real draft against those targets). The CEO
Reviewer is the terminal gate: REJECT sends the draft back through the
Generator + Doctor with the rejection reasons attached, up to a fixed
attempt budget, before the pipeline is forced to ship its best attempt.
"""

from __future__ import annotations

from script_agent_v2 import context as context_module
from script_agent_v2 import outputs
from script_agent_v2.engines import (
    audience_engine,
    ceo_reviewer,
    curiosity_engine,
    doctor,
    emotion_engine,
    fact_engine,
    generator,
    knowledge_engine,
    memory_engine,
    originality_engine,
    psychology_engine,
    retention_engine,
    story_dna_engine,
    visual_engine,
)
from script_agent_v2.llm import LLM

MAX_CEO_ATTEMPTS = 3


def run() -> dict:
    ctx = context_module.build_context()
    context_dict = ctx.as_dict()
    if not context_dict["topic"]:
        raise SystemExit("Video CEO somut video fikri üretmedi; Script Agent V2 çalışamaz.")

    llm = LLM()

    knowledge = knowledge_engine.run(context_dict, llm)
    story_dna_plan = story_dna_engine.run(context_dict, ctx.story_dna, ctx.memory)
    psychology_plan = psychology_engine.plan(context_dict)
    audience_profile = audience_engine.run(context_dict)
    curiosity_plan = curiosity_engine.plan(story_dna_plan)
    retention_plan = retention_engine.plan(context_dict)
    emotion_plan = emotion_engine.plan(story_dna_plan)
    originality_plan = originality_engine.plan(context_dict)
    visual_plan = visual_engine.plan(context_dict)
    fact_ledger = fact_engine.build_ledger(knowledge)
    memory_hints = memory_engine.hints_for_generation(ctx.memory)

    feedback: list[str] | None = None
    rejected_history: list[dict] = []
    script: dict = {}
    evaluations: dict = {}
    ceo_review: dict = {}
    attempts_used = 0

    for attempt in range(1, MAX_CEO_ATTEMPTS + 1):
        attempts_used = attempt
        script = generator.generate(
            context_dict, llm, knowledge, story_dna_plan, psychology_plan, audience_profile,
            curiosity_plan, retention_plan, emotion_plan, originality_plan,
            fact_ledger, memory_hints, feedback,
        )
        script = doctor.review_and_fix(
            script, llm, curiosity_plan, retention_plan, emotion_plan, originality_plan, fact_ledger,
        )

        sections = script.get("sections", [])
        evaluations = {
            "curiosity": curiosity_engine.evaluate(sections, curiosity_plan),
            "retention": retention_engine.evaluate(sections, retention_plan),
            "emotion": emotion_engine.evaluate(sections, emotion_plan),
            "originality": originality_engine.evaluate(sections, originality_plan, llm),
            "fact": fact_engine.evaluate(sections, fact_ledger),
        }
        ceo_review = ceo_reviewer.review(script, evaluations)

        if ceo_review["decision"] == "APPROVE":
            break

        rejected_history.append({
            "attempt": attempt,
            "ceo_score": ceo_review["ceo_score"],
            "reasons": ceo_review["reasons"] + ceo_review["floor_violations"],
        })
        feedback = ceo_review["reasons"] + ceo_review["floor_violations"]

        if script.get("source_mode") == "rule_based_fallback":
            # Deterministic fallback has no way to respond to CEO feedback
            # without an LLM — retrying would just reproduce the same draft.
            rejected_history[-1]["reasons"].append(
                "GEMINI_API_KEY (ve OPENAI_API_KEY, GROQ_API_KEY) yok; kural tabanlı taslak yeniden denenerek iyileştirilemez."
            )
            break

    visuals = visual_engine.generate(script.get("sections", []), knowledge, visual_plan, llm)

    updated_memory = memory_engine.record(ctx.memory, script, ceo_review, evaluations, story_dna_plan)
    memory_engine.save(updated_memory, context_module.MEMORY_PATH)

    outputs.write_all(
        script, context_dict, knowledge, story_dna_plan, evaluations, ceo_review,
        visuals, attempts_used, rejected_history,
    )

    print(f"SCRIPT_AGENT_V2_STATUS={ceo_review['decision']}")
    print(f"SCRIPT_AGENT_V2_CEO_SCORE={ceo_review['ceo_score']}")
    print(f"SCRIPT_AGENT_V2_ATTEMPTS={attempts_used}")
    print(f"SCRIPT_AGENT_V2_TITLE={script.get('title', '')}")
    print(f"SCRIPT_AGENT_V2_MODE={script.get('source_mode', 'unknown')}")
    print(f"REPORT={context_module.OUTPUT_DIR / 'script.md'}")

    return {
        "script": script,
        "ceo_review": ceo_review,
        "evaluations": evaluations,
    }
