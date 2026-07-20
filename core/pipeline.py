"""Orchestration: chunk -> rewrite (parallel) -> post-pass -> verify -> score.

Only the rewrite step spends tokens. Keyword verification retries are
per-chunk and happen at most once, so a lost keyword costs one extra small
call instead of a full-document redo.
"""
import asyncio

import engine
from . import chunking, diffing, postpass, prompts, scorer

_CONCURRENCY = asyncio.Semaphore(3)


async def _rewrite_chunk(chunk: str, mode: str, keywords: list[str], variant: int) -> tuple[str, list[str]]:
    # only enforce keywords that actually occur in this chunk
    local_kw = [k for k in keywords if k.lower() in chunk.lower()]
    async with _CONCURRENCY:
        out = await engine.rewrite(prompts.build_prompt(chunk, mode, local_kw, variant))
    out = postpass.clean(out, local_kw)
    missing = postpass.missing_keywords(out, local_kw)
    if missing:
        async with _CONCURRENCY:
            out = await engine.rewrite(prompts.retry_prompt(chunk, mode, local_kw, missing))
        out = postpass.clean(out, local_kw)
        missing = postpass.missing_keywords(out, local_kw)
    return out, missing


async def humanize(text: str, mode: str, keywords: list[str], variants: int = 1) -> dict:
    text = text.strip()
    chunks = chunking.split_chunks(text, max_words=engine.CHUNK_WORDS)
    if not chunks:
        raise ValueError("No text to humanize")
    variants = max(1, min(variants, 3))
    formal = mode in ("formal", "academic")

    async def one_variant(v: int) -> dict:
        results = await asyncio.gather(
            *[_rewrite_chunk(c, mode, keywords, v) for c in chunks]
        )
        out = "\n\n".join(r[0] for r in results)
        warnings = []
        lost = sorted({k for r in results for k in r[1]})
        if lost:
            warnings.append("Could not keep these locked terms verbatim: " + ", ".join(lost))
        return {
            "text": out,
            "diff": diffing.diff_segments(text, out),
            "score": scorer.score(out, formal=formal),
            "warnings": warnings,
        }

    out_variants = await asyncio.gather(*[one_variant(v) for v in range(variants)])
    return {
        "score_before": scorer.score(text),
        "variants": out_variants,
        "chunks": len(chunks),
    }
