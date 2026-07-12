"""9. VISUAL THINKING ENGINE

Every paragraph must answer: "What is the viewer watching right now?"
Generates a visual idea, camera idea, scene idea and b-roll suggestions for
every section — via GROQ when available, otherwise a deterministic
documentary shot-bank keyed to the section's role and the entities the
Knowledge Engine already found.
"""

from __future__ import annotations

from script_agent_v2.llm import LLM

SYSTEM_PROMPT = (
    "Sen SHP Visual Thinking Engine'sin: bir belgesel yönetmenisin. Sana bölüm adı ve seslendirme metni "
    "vereceğim. İzleyicinin o an ekranda ne gördüğünü tarif et. JSON döndür: "
    "{\"visual_idea\": \"...\", \"camera_idea\": \"...\", \"scene_idea\": \"...\", \"b_roll\": [\"...\", \"...\"]}"
)

SHOT_BANK_BY_ROLE = {
    "hook": {
        "visual_idea": "Tek çarpıcı obje veya manzara, ekranı dolduran makro çekim.",
        "camera_idea": "Yavaş yakınlaşan (slow push-in) tek plan, kesme yok.",
        "scene_idea": "Karanlık zemin üzerinde ana obje ışıkla vurgulanır.",
        "b_roll": ["Konu objesinin makro detay çekimi", "Atmosferik ortam planı"],
    },
    "origin": {
        "visual_idea": "Coğrafi köken haritası üzerinde animasyonlu işaretleme.",
        "camera_idea": "Yukarıdan aşağı harita hareketi (top-down pan).",
        "scene_idea": "Dönemin arşiv görselleri veya illüstrasyonlarla geçiş.",
        "b_roll": ["Tarihi harita animasyonu", "Dönem gravürü/illüstrasyonu"],
    },
    "conflict": {
        "visual_idea": "Karşıt iki güç veya taraf arasında görsel gerilim kurulur.",
        "camera_idea": "Sert kesmeler, kısa planlar, ritmi hızlandırır.",
        "scene_idea": "Kararan ışık, dramatik gölgeler, silüet yeniden canlandırma.",
        "b_roll": ["Silüet reenactment", "Dönem belgesi/kayıt close-up'ı"],
    },
    "mystery": {
        "visual_idea": "Eksik parça veya cevaplanmamış detay ekranda büyütülür.",
        "camera_idea": "Yavaş rack focus; net olmayan arka plandan nesneye odak.",
        "scene_idea": "Arşiv fotoğrafı üzerinde soru işareti grafiği veya vurgulama efekti.",
        "b_roll": ["Arşiv belge close-up'ı", "Bilim insanı/araştırmacı çalışma planı"],
    },
    "reveal": {
        "visual_idea": "Ana cevabı temsil eden görsel net ve büyük şekilde ortaya çıkar.",
        "camera_idea": "Ani zoom-out veya ışık patlaması hissi veren geçiş.",
        "scene_idea": "Önceki karanlık/belirsiz sahneden aydınlık/net sahneye geçiş.",
        "b_roll": ["Modern kanıt/örnek görüntüsü", "Bilimsel görselleştirme/grafik"],
    },
    "final": {
        "visual_idea": "Geniş, sakin bir kapanış planı; hikâyenin bugüne bağlandığı görüntü.",
        "camera_idea": "Yavaş uzaklaşan (pull-out) geniş açı plan.",
        "scene_idea": "Gün ışığına dönüş; sıcak renk paleti.",
        "b_roll": ["Günümüz/modern kullanım görüntüsü", "Geniş açı doğa/mekan planı"],
    },
}

ROLE_ORDER = ["hook", "origin", "conflict", "mystery", "reveal", "final"]


def plan(context_dict: dict) -> dict:
    return {"shot_bank": SHOT_BANK_BY_ROLE, "role_order": ROLE_ORDER}


def _role_for_index(index: int, total: int) -> str:
    if index == 0:
        return "hook"
    if index == total - 1:
        return "final"
    position = index / max(1, total - 1)
    if position < 0.35:
        return "origin"
    if position < 0.55:
        return "conflict"
    if position < 0.8:
        return "mystery"
    return "reveal"


def generate(sections: list[dict], knowledge: dict, visual_plan: dict, llm: LLM) -> list[dict]:
    shot_bank = visual_plan.get("shot_bank", SHOT_BANK_BY_ROLE)
    total = len(sections)
    entities = [p.get("name", "") for p in knowledge.get("locations", [])] + [
        p.get("name", "") for p in knowledge.get("key_people", [])
    ]
    entities = [e for e in entities if e]

    visuals = []
    for index, section in enumerate(sections):
        role = _role_for_index(index, total)
        text = str(section.get("voiceover", ""))

        result = llm.complete_json(
            SYSTEM_PROMPT,
            f"Bölüm: {section.get('name', '')}\nSeslendirme: {text}",
            temperature=0.6,
        )
        if result and isinstance(result, dict) and result.get("visual_idea"):
            entry = {
                "section": section.get("name", ""),
                "visual_idea": result.get("visual_idea", ""),
                "camera_idea": result.get("camera_idea", ""),
                "scene_idea": result.get("scene_idea", ""),
                "b_roll": result.get("b_roll", []),
            }
        else:
            template = shot_bank.get(role, shot_bank["mystery"])
            b_roll = list(template["b_roll"])
            if entities:
                b_roll.append(f"{entities[index % len(entities)]} ile ilgili görsel malzeme")
            entry = {
                "section": section.get("name", ""),
                "visual_idea": template["visual_idea"],
                "camera_idea": template["camera_idea"],
                "scene_idea": template["scene_idea"],
                "b_roll": b_roll,
            }
        entry["role"] = role
        visuals.append(entry)
    return visuals
