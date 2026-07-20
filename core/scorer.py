"""Heuristic AI-likeness scorer.

This is an honest local estimate based on the statistical signals real
detectors weigh (sentence-length variance, stock AI vocabulary, punctuation
tells, formulaic transitions). It is NOT a detector and is labelled as a
heuristic in the UI — unlike humanizeai.pro's built-in checker, it does not
pretend to be GPTZero.
"""
import re
import statistics

from .prompts import BANNED_WORDS

TRANSITION_OPENERS = (
    "however", "moreover", "furthermore", "additionally", "in addition",
    "in conclusion", "overall", "therefore", "thus", "consequently",
    "notably", "importantly", "ultimately", "firstly", "secondly",
)

_WORD = re.compile(r"[A-Za-z']+")


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if _WORD.search(p)]


def score(text: str, formal: bool = False) -> dict:
    """AI-likeness estimate 0-100. `formal=True` (academic/formal registers)
    drops the contraction signal — those registers legitimately avoid them."""
    words = _WORD.findall(text.lower())
    n_words = len(words)
    sents = _sentences(text)
    if n_words < 20 or len(sents) < 2:
        return {
            "score": None,
            "verdict": "Text too short to score",
            "metrics": {},
        }

    lengths = [len(_WORD.findall(s)) for s in sents]
    mean_len = statistics.mean(lengths)
    burstiness = (statistics.stdev(lengths) / mean_len) if len(lengths) > 1 and mean_len else 0.0

    per_k = 1000 / n_words
    ai_hits = sum(text.lower().count(w) for w in BANNED_WORDS)
    ai_density = ai_hits * per_k
    dash_density = text.count("—") * per_k
    openers = sum(
        1 for s in sents if s.lower().lstrip("\"'").startswith(TRANSITION_OPENERS)
    )
    opener_frac = openers / len(sents)
    contractions = len(re.findall(r"\b\w+'(?:t|s|re|ve|ll|d|m)\b", text))
    contraction_density = contractions * per_k

    # Each component in 0..1, weighted into a 0-100 AI-likeness estimate.
    c_burst = 1 - min(burstiness / 0.65, 1.0)          # uniform sentences -> AI-ish
    c_vocab = min(ai_density / 8.0, 1.0)               # stock AI vocabulary
    c_dash = min(dash_density / 4.0, 1.0)              # em-dash habit
    c_trans = min(opener_frac / 0.30, 1.0)             # formulaic transitions
    c_contr = 1 - min(contraction_density / 8.0, 1.0)  # no contractions -> stiff

    if formal:
        raw = 0.34 * c_burst + 0.22 * c_vocab + 0.12 * c_dash + 0.18 * c_trans
        value = round(100 * raw / 0.86)
    else:
        value = round(100 * (0.34 * c_burst + 0.22 * c_vocab + 0.12 * c_dash
                             + 0.18 * c_trans + 0.14 * c_contr))

    if value <= 25:
        verdict = "Reads human"
    elif value <= 50:
        verdict = "Mostly human"
    elif value <= 75:
        verdict = "Mixed signals"
    else:
        verdict = "Reads AI-written"

    metrics: dict = {
            "burstiness": {
                "label": "Sentence rhythm",
                "value": round(burstiness, 2),
                "good": burstiness >= 0.45,
                "hint": "variation in sentence length; humans mix short and long",
            },
            "ai_vocab": {
                "label": "AI vocabulary",
                "value": round(ai_density, 1),
                "good": ai_density < 2,
                "hint": "stock AI words per 1,000 words",
            },
            "em_dashes": {
                "label": "Em-dashes",
                "value": round(dash_density, 1),
                "good": dash_density < 1,
                "hint": "em-dashes per 1,000 words",
            },
            "transitions": {
                "label": "Formulaic openers",
                "value": round(opener_frac * 100),
                "good": opener_frac < 0.15,
                "hint": "% of sentences opening with However/Moreover/etc.",
            },
    }
    if not formal:
        metrics["contractions"] = {
            "label": "Contractions",
            "value": round(contraction_density, 1),
            "good": contraction_density >= 3,
            "hint": "contractions per 1,000 words; stiff text has none",
        }

    return {
        "score": value,
        "verdict": verdict,
        "metrics": metrics,
        "words": n_words,
        "sentences": len(sents),
    }
