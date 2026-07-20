"""Paragraph-aware chunking so long documents process in parallel pieces.

No word limits anywhere: a 10,000-word article just becomes ~12 chunks.
"""

MAX_CHUNK_WORDS = 900


def split_chunks(text: str, max_words: int = MAX_CHUNK_WORDS) -> list[str]:
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []
    chunks: list[str] = []
    current: list[str] = []
    count = 0
    for p in paragraphs:
        p_words = len(p.split())
        if current and count + p_words > max_words:
            chunks.append("\n\n".join(current))
            current, count = [], 0
        current.append(p)
        count += p_words
    if current:
        chunks.append("\n\n".join(current))
    return chunks
