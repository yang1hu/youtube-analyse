import re
from dataclasses import dataclass


@dataclass(frozen=True)
class StoryRecapAnalysis:
    premise: str
    protagonist: str
    central_conflict: str
    turning_points: list[str]
    retention_hooks: list[str]
    packaging_notes: list[str]


def analyze_story_recap(title: str, transcript_text: str, description: str = "") -> StoryRecapAnalysis:
    text = _clean_text(transcript_text or description)
    sentences = _sentences(text)
    title_notes = _title_packaging_notes(title)

    return StoryRecapAnalysis(
        premise=_pick_premise(title=title, sentences=sentences),
        protagonist=_pick_protagonist(sentences),
        central_conflict=_pick_conflict(title=title, sentences=sentences),
        turning_points=_pick_turning_points(sentences),
        retention_hooks=_pick_retention_hooks(title=title, sentences=sentences),
        packaging_notes=title_notes,
    )


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if len(part.strip()) >= 35]


def _pick_premise(title: str, sentences: list[str]) -> str:
    title_premise = title.replace(" - Manhwa Recap", "").strip()
    setup = _first_matching(
        sentences[:40],
        ["banquet", "family", "engagement", "waiter", "billionaire", "thought"],
    )
    if setup:
        return f"{title_premise}. Setup: {setup}"
    return title_premise


def _pick_protagonist(sentences: list[str]) -> str:
    first_person = _first_matching(sentences[:60], ["i stood", "i was", "i did", "my ", " me "])
    if first_person:
        return first_person
    return sentences[0] if sentences else "The protagonist is not clear from the available script."


def _pick_conflict(title: str, sentences: list[str]) -> str:
    conflict = _first_matching(
        sentences,
        [
            "refused to let",
            "hidden truth",
            "fraud",
            "cheater",
            "parasite",
            "financial control",
            "threat",
            "contract",
            "could not leave",
            "wouldn't let",
            "betrayed",
            "humiliated",
        ],
    )
    if conflict:
        return conflict
    return title.replace(" - Manhwa Recap", "").strip()


def _pick_turning_points(sentences: list[str]) -> list[str]:
    keywords = [
        "suddenly",
        "then",
        "but",
        "however",
        "realized",
        "discovered",
        "heard",
        "thought",
        "refused",
        "secret",
        "truth",
        "contract",
        "marriage",
    ]
    return _top_unique_matches(sentences, keywords, limit=5, start_ratio=0.05)


def _pick_retention_hooks(title: str, sentences: list[str]) -> list[str]:
    hooks = _title_packaging_notes(title)
    script_hooks = _top_unique_matches(
        sentences,
        ["refused", "secret", "thought", "billionaire", "ice queen", "leave", "truth", "betrayed", "danger"],
        limit=3,
        start_ratio=0.0,
    )
    return (hooks + script_hooks)[:5]


def _title_packaging_notes(title: str) -> list[str]:
    notes: list[str] = []
    lowered = title.lower()
    if "hearing my thoughts" in lowered or "thoughts" in lowered:
        notes.append("Uses a supernatural/private-information hook: hearing hidden thoughts.")
    if "ice queen" in lowered:
        notes.append("Uses a cold-powerful-woman archetype to create curiosity and tension.")
    if "refused to let me leave" in lowered:
        notes.append("Promises forced proximity, control, and unresolved romantic conflict.")
    if "billionaire" in lowered:
        notes.append("Adds wealth/status fantasy for escapist appeal.")
    return notes or ["The title packages the story around a clear high-stakes promise."]


def _first_matching(sentences: list[str], keywords: list[str]) -> str:
    lowered_keywords = [keyword.lower() for keyword in keywords]
    for sentence in sentences:
        lowered = f" {sentence.lower()} "
        if any(keyword in lowered for keyword in lowered_keywords):
            return sentence
    return ""


def _top_unique_matches(sentences: list[str], keywords: list[str], limit: int, start_ratio: float) -> list[str]:
    if not sentences:
        return []

    start = int(len(sentences) * start_ratio)
    lowered_keywords = [keyword.lower() for keyword in keywords]
    matches: list[str] = []
    seen: set[str] = set()

    for sentence in sentences[start:]:
        lowered = sentence.lower()
        if not any(keyword in lowered for keyword in lowered_keywords):
            continue
        normalized = re.sub(r"[^a-z0-9]+", " ", lowered)[:80]
        if normalized in seen:
            continue
        seen.add(normalized)
        matches.append(sentence[:180])
        if len(matches) >= limit:
            break

    return matches
