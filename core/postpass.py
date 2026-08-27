"""Deterministic post-pass: strips residual AI tells the model left behind.

Costs zero tokens — runs after every rewrite.
"""
import re

# word/phrase -> plain replacement (lowercase; capitalisation is preserved)
SWAPS = {
    r"\butilize\b": "use",
    r"\butilizes\b": "uses",
    r"\butilizing\b": "using",
    r"\butilization\b": "use",
    r"\bleverage\b": "use",
    r"\bleverages\b": "uses",
    r"\bleveraging\b": "using",
    r"\bcommence\b": "start",
    r"\bcommences\b": "starts",
    r"\bin order to\b": "to",
    r"\ba myriad of\b": "many",
    r"\bmyriad of\b": "many",
    r"\bdelve into\b": "dig into",
    r"\bdelves into\b": "digs into",
    r"\bfurthermore,?\s": "",
    r"\bmoreover,?\s": "",
    r"\badditionally,\s": "",
    r"\bit is important to note that\s": "",
    r"\bit's important to note that\s": "",
    r"\bin conclusion,?\s": "",
    r"\bin today's (?:fast-paced |ever-changing |digital )?world,?\s": "",
}

CONTRACTIONS = {
    r"\bdo not\b": "don't",
    r"\bdoes not\b": "doesn't",
    r"\bdid not\b": "didn't",
    r"\bcannot\b": "can't",
    r"\bwill not\b": "won't",
    r"\bwould not\b": "wouldn't",
    r"\bshould not\b": "shouldn't",
    r"\bcould not\b": "couldn't",
    r"\bis not\b": "isn't",
    r"\bare not\b": "aren't",
    r"\bwas not\b": "wasn't",
    r"\bwere not\b": "weren't",
    r"\bhas not\b": "hasn't",
    r"\bhave not\b": "haven't",
    r"\bhad not\b": "hadn't",
}


def _apply_cased(text: str, pattern: str, repl: str) -> str:
    def sub(m: re.Match) -> str:
        s = m.group(0)
        if not repl:
            return ""
        if s[0].isupper():
            return repl[0].upper() + repl[1:]
        return repl
    return re.sub(pattern, sub, text, flags=re.IGNORECASE)


def _protect(text: str, keywords: list[str]):
    """Mask locked keywords so swaps never touch them."""
    masks = {}
    for i, kw in enumerate(keywords):
        token = f"\x00K{i}\x00"
        if kw in text:
            masks[token] = kw
            text = text.replace(kw, token)
    return text, masks


def clean(text: str, keywords: list[str] | None = None) -> str:
    keywords = keywords or []
    text, masks = _protect(text, keywords)

    # em-dashes read as an AI tell; turn spaced ones into commas, bare into space.
    # BUT never touch a dash sitting between digits — that is a numeric range or ratio
    # (6-8 weeks, 550-795 MPa, 1/16) and rewriting it to a comma corrupts the value.
    text = re.sub(r"(?<!\d)\s*—\s*(?!\d)", ", ", text)
    text = re.sub(r"(?<!\d)\s*–\s*(?!\d)", ", ", text)

    for pat, repl in SWAPS.items():
        text = _apply_cased(text, pat, repl)
    for pat, repl in CONTRACTIONS.items():
        text = _apply_cased(text, pat, repl)

    # tidy artifacts from phrase removals: double spaces, ", ," etc.
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r",\s*,", ",", text)
    # a removed sentence-opener can leave a lowercase start; capitalise it
    text = re.sub(
        r"(^|[.!?]\s+)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        text,
    )

    for token, kw in masks.items():
        text = text.replace(token, kw)
    return text.strip()


def missing_keywords(text: str, keywords: list[str]) -> list[str]:
    low = text.lower()
    return [k for k in keywords if k.lower() not in low]
