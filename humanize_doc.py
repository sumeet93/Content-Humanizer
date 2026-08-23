#!/usr/bin/env python3
"""Humanize a whole Markdown/MDX document — prose only, structure-safe.

Reusable CLI wrapper around the Content-Humanizer core. It:
  - protects headings, tables, fenced code, <script> (e.g. JSON-LD) and YAML
    frontmatter ATOMICALLY (never rewritten),
  - humanizes only the prose paragraphs, all blocks CONCURRENTLY (fast),
  - auto-locks technical terms (spec codes, numbers+units, acronyms, emails,
    URLs) so facts survive verbatim; add more with --keywords,
  - REJECTS model chatter/refusals ("here's the rewrite", "could you paste",
    "plain rewrite task", ...) and keeps the original block instead,
  - repairs dash artifacts and strips any residual leaked chatter sentence.

Usage:
    python humanize_doc.py <in.md> <out.md> [--mode formal] [--keywords "Term A,Term B"]
Env:
    HUMANIZER_ENGINE=claude-cli|api   HUMANIZER_MODEL=...   HUMANIZER_CONCURRENCY=8
"""
import sys, os, re, asyncio, argparse

_ORIG_CWD = os.getcwd()
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
os.chdir(_HERE)
os.environ.pop("CLAUDECODE", None)   # allow nested `claude` CLI calls
from core import pipeline, scorer  # noqa

# --- generic locked-term extraction (domain-agnostic) ---
_TECH = re.compile(
    r"\b("
    r"UNS\s?[A-Z]?\d{4,6}|W\.?Nr\.?\s?[\d.]+|"                     # material/spec codes
    r"(?:ASTM|ASME|ISO|EN|DIN|API|NACE|IEC|SAE|MIL|AMS|BS|JIS|GB)\s?[A-Z]?[\d][\d.\-/]*|"
    r"[A-Z]{2,6}\d{2,6}[A-Z]?|"                                    # code-like tokens e.g. N10276, A312
    r"\d[\d,]*\.?\d*\s?(?:psi|PSI|bar|kPa|MPa|mm|cm|in|ft|mm²|°C|°F|K|kg|lb|%|Hz|V|A|W|rpm|µm|Ra)|" # numbers+units
    r"[A-Z][A-Za-z]+(?:[- ][A-Z][A-Za-z]+){1,3}®?|"               # multi-word proper nouns / brands
    r"[A-Z]{2,8}|"                                                 # acronyms
    r"[\w.+-]+@[\w.-]+\.\w+|https?://\S+"                          # emails / urls
    r")\b"
)
def auto_locked_terms(text, extra):
    terms = set(m.group(0).strip() for m in _TECH.finditer(text))
    terms |= set(t.strip() for t in extra if t.strip())
    # keep the longest / most specific, cap to keep prompts small
    return sorted(terms, key=len, reverse=True)[:80]

# --- chatter / process-leak detection ---
_CHATTER = re.compile(r"(?i)(could you (paste|provide|share)|the passage you'?ve provided|"
    r"here'?s the (rewrit|revised)|let me (write|rewrite|do)|i'?ll just (do|rewrite)|do it directly|"
    r"no ambiguity, so|as an ai|i cannot|i can'?t (help|rewrite)|rewritten passage|paste the full|"
    r"provide the full (source|passage)|^\s*(sure|okay|here)\b|two-sentence|plain rewrite task|"
    r"rewrite task,? (not|with)|not (a )?(code|coding) (work|task)|feature work|no code|"
    r"the rule says|keep them verbatim|final rewrite|this is a (plain|simple|straightforward) (rewrite|task))")

def _bad_rewrite(out, original):
    if not out or not out.strip(): return True
    if _CHATTER.search(out): return True
    ow, iw = len(out.split()), len(original.split())
    if iw >= 12 and ow < 0.55 * iw: return True
    if out.count("?") > original.count("?") + 1: return True
    return False

_SUFFIX_CAPS = re.compile(r"\b(Inc|Co|Corp|Ltd|Mfg|Ltda|GmbH|Pvt)\.(\s+)"
    r"(Is|Or|And|Has|Have|Was|Were|Are|Builds|Makes|Made|Offers|Provides|Supplies|"
    r"Operates|Of|The|A|An|To|In|For|With|As|At|That|Which|Based)\b")
def _fix_artifacts(t):
    t = re.sub(r"\b(\d{1,3}),\s*(\d{1,3})\s+(week|hour|day|psi|bar|mm|month|year)", r"\1-\2 \3", t)
    # company suffixes (Inc./Co./Ltd.) mis-read as sentence ends -> next function word wrongly
    # capitalized; only lowercase a known function/verb set so real new sentences stay intact.
    t = _SUFFIX_CAPS.sub(lambda m: f"{m.group(1)}.{m.group(2)}{m.group(3)[0].lower()}{m.group(3)[1:]}", t)
    out = []
    for ln in t.split("\n"):
        if _CHATTER.search(ln) and not ln.strip().startswith(("|", "#", "<", "{", "\"")):
            cleaned = re.sub(r"[^.!?]*\b(plain rewrite task|rewritten passage|here'?s the rewrit|"
                r"let me (write|rewrite|do)|i'?ll just (do|rewrite)|do it directly|no ambiguity, so|"
                r"the rule says|keep them verbatim|final rewrite|could you (paste|provide)|"
                r"the passage you'?ve provided|this is a (plain|simple|straightforward) (rewrite|task))"
                r"[^.!?]*[.!?]\s*", "", ln, flags=re.I).strip()
            if cleaned: out.append(cleaned)
        else:
            out.append(ln)
    return "\n".join(out)

# --- structure-safe segmentation ---
def _is_protected(line):
    s = line.strip()
    if not s: return None
    if s.startswith(("#", "|", ">")): return True
    if re.match(r'^(<|\{|\[)', s): return True
    if re.match(r'^[-*+]\s', s) and len(s) < 120: return True
    if re.match(r'^\d+\.\s', s) and len(s) < 120: return True
    return False

def segment(md):
    lines = md.split("\n"); segs, buf = [], []
    in_fence = in_script = in_fm = False
    def flush():
        if buf: segs.append(("prose", "\n".join(buf))); buf.clear()
    for idx, ln in enumerate(lines):
        st, low = ln.strip(), ln.strip().lower()
        if idx == 0 and st == "---":
            flush(); in_fm = True; segs.append(("keep", ln)); continue
        if in_fm:
            segs.append(("keep", ln))
            if st == "---": in_fm = False
            continue
        if not in_fence and "<script" in low:
            flush(); in_script = True; segs.append(("keep", ln))
            if "</script>" in low: in_script = False
            continue
        if in_script:
            segs.append(("keep", ln))
            if "</script>" in low: in_script = False
            continue
        if st.startswith(("```", "~~~")):
            flush(); in_fence = not in_fence; segs.append(("keep", ln)); continue
        if in_fence:
            segs.append(("keep", ln)); continue
        p = _is_protected(ln)
        if p is None: flush(); segs.append(("keep", ln))
        elif p: flush(); segs.append(("keep", ln))
        else: buf.append(ln)
    flush()
    return segs

async def run(inp, outp, mode, extra_kw, us_spelling=False):
    _post = (lambda t: t)
    if us_spelling:
        from locale_us import normalize as _post
    md = open(inp).read()
    kw = auto_locked_terms(md, extra_kw)
    segs = segment(md)
    prose_idx = [i for i, (k, _) in enumerate(segs) if k == "prose" and len(segs[i][1].split()) >= 12]
    conc = int(os.environ.get("HUMANIZER_CONCURRENCY", "8"))
    sem = asyncio.Semaphore(conc)
    kept = 0
    async def do_block(i):
        nonlocal kept
        block = segs[i][1]
        async with sem:
            try:
                r = await pipeline.humanize(block, mode, kw, 1)
            except Exception as e:
                sys.stderr.write(f"[warn] block {i} kept: {e}\n"); kept += 1; return
        out_block = r["variants"][0]["text"]
        if _bad_rewrite(out_block, block):
            sys.stderr.write(f"[reject] block {i} chatter/short — keeping original\n"); kept += 1
        else:
            segs[i] = ("prose", _fix_artifacts(out_block))
    await asyncio.gather(*[do_block(i) for i in prose_idx])
    out = _post(_fix_artifacts("\n".join(t for _, t in segs)))
    os.makedirs(os.path.dirname(os.path.abspath(outp)) or ".", exist_ok=True)
    open(outp, "w").write(out)
    before = "\n\n".join(t for k, t in segment(md) if k == "prose")
    after = "\n\n".join(t for k, t in segs if k == "prose")
    print(f"{os.path.basename(inp)}: prose blocks={len(prose_idx)} kept={kept} | "
          f"AI-score {scorer.score(before)['score']}->{scorer.score(after)['score']} | locked_terms={len(kw)}")

def main():
    ap = argparse.ArgumentParser(description="Humanize a Markdown document (prose only, structure-safe, concurrent).")
    ap.add_argument("infile"); ap.add_argument("outfile")
    ap.add_argument("--mode", default="formal", help="standard|formal|informal|academic|shorten|expand")
    ap.add_argument("--keywords", default="", help="comma-separated extra terms to lock verbatim")
    ap.add_argument("--us-spelling", action="store_true", help="normalize British -> US spelling (US-audience docs)")
    a = ap.parse_args()
    def _abs(p): return p if os.path.isabs(p) else os.path.normpath(os.path.join(_ORIG_CWD, p))
    asyncio.run(run(_abs(a.infile), _abs(a.outfile), a.mode,
                    a.keywords.split(",") if a.keywords else [], a.us_spelling))

if __name__ == "__main__":
    main()
