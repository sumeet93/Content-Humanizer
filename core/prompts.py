"""Prompt construction for the rewrite engine.

Kept deliberately compact — the instruction block is ~150 tokens so the
per-chunk overhead stays small regardless of document size.
"""

MODES = {
    "standard": "Keep the original register.",
    "formal": "Use a professional, formal register. No slang.",
    "informal": "Use a relaxed, conversational register, like explaining to a colleague.",
    "academic": "Use precise academic prose. Hedge claims appropriately. No first person.",
    "shorten": "Cut it to roughly 70% of the original length. Drop filler, keep every fact.",
    "expand": "Expand it by about a third by unpacking existing points; stay under 140% of the original length. Do not invent new facts.",
}

BANNED_WORDS = [
    "delve", "tapestry", "realm", "robust", "seamless", "seamlessly",
    "leverage", "utilize", "foster", "underscore", "testament", "pivotal",
    "moreover", "furthermore", "additionally", "notably", "in conclusion",
    "in today's world", "it's important to note", "landscape",
]

_RULES = """Rewrite the passage so it reads like a skilled human wrote it, not an AI.
Rules:
- Keep every fact, claim, name and number exactly as given. Add nothing, drop nothing.
- Vary sentence length a lot: short punchy sentences mixed with longer ones. An occasional fragment is fine.
- Use contractions naturally.
- Plain concrete words. Never use: {banned}.
- No em-dashes.
- Don't open consecutive sentences the same way. No formulaic transitions.
- Keep paragraph breaks where they are.
- {mode}"""


def build_prompt(text: str, mode: str, keywords: list[str], variant: int = 0) -> str:
    rules = _RULES.format(banned=", ".join(BANNED_WORDS), mode=MODES.get(mode, MODES["standard"]))
    parts = [rules]
    if keywords:
        parts.append("These terms must appear verbatim, unchanged: " + "; ".join(keywords) + ".")
    if variant:
        parts.append(f"This is alternative take #{variant + 1}: use noticeably different wording and rhythm than an obvious first rewrite would.")
    parts.append(
        "Reply with the rewritten passage only. No preamble, no commentary, no exploratory "
        "reasoning, no quotes around it - your entire reply IS the rewrite.\n\nPASSAGE:\n<<<\n"
        + text + "\n>>>"
    )
    return "\n".join(parts)


def retry_prompt(text: str, mode: str, keywords: list[str], missing: list[str]) -> str:
    base = build_prompt(text, mode, keywords)
    return (
        "Your previous rewrite dropped these required terms: "
        + "; ".join(missing)
        + ". They MUST appear verbatim.\n\n" + base
    )
