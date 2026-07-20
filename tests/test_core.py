import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import chunking, diffing, postpass, prompts, scorer  # noqa: E402


# ---------- postpass ----------

def test_swaps_and_contractions():
    out = postpass.clean("We will utilize the tool. It does not fail.")
    assert "utilize" not in out
    assert "use the tool" in out
    assert "doesn't fail" in out


def test_em_dash_removed():
    out = postpass.clean("Pipes matter — a lot.")
    assert "—" not in out
    assert "Pipes matter, a lot." == out


def test_sentence_opener_removed_and_recapitalised():
    out = postpass.clean("Furthermore, the pipes resist corrosion.")
    assert out.startswith("The pipes")


def test_locked_keyword_protected():
    out = postpass.clean("Our Utilize Pro brand helps you utilize data.", ["Utilize Pro"])
    assert "Utilize Pro" in out
    assert "use data" in out


def test_missing_keywords():
    assert postpass.missing_keywords("hello world", ["world", "steel pipe"]) == ["steel pipe"]


# ---------- scorer ----------

AI_TEXT = (
    "Moreover, it is important to understand the landscape. "
    "Furthermore, the solution is robust and seamless. "
    "Additionally, we must delve into the topic. "
    "Moreover, the framework is pivotal for success. "
    "Furthermore, stakeholders should leverage synergies."
)

HUMAN_TEXT = (
    "Honestly? The pipe cracked on day two. We'd been warned. "
    "My supplier told me the schedule 40 stuff wasn't rated for that pressure, "
    "and he was right, though I didn't want to hear it at the time. Lesson learned. "
    "Now I spec everything twice and it hasn't happened since."
)


def test_ai_text_scores_higher_than_human_text():
    ai = scorer.score(AI_TEXT)["score"]
    human = scorer.score(HUMAN_TEXT)["score"]
    assert ai > human
    assert ai > 55
    assert human < 45


def test_short_text_not_scored():
    assert scorer.score("Too short.")["score"] is None


# ---------- chunking ----------

def test_chunking_respects_paragraphs():
    para = "word " * 400
    text = "\n\n".join([para, para, para])
    chunks = chunking.split_chunks(text, max_words=900)
    assert len(chunks) == 2
    assert "\n\n".join(chunks).count("word") == 1200


def test_single_short_text_one_chunk():
    assert chunking.split_chunks("Just one small paragraph.") == ["Just one small paragraph."]


# ---------- diffing ----------

def test_diff_marks_changes():
    segs = diffing.diff_segments("the quick brown fox", "the slow brown fox")
    changed = "".join(s["text"] for s in segs if s["changed"])
    same = "".join(s["text"] for s in segs if not s["changed"])
    assert "slow" in changed
    assert "brown fox" in same


# ---------- prompts ----------

def test_prompt_contains_text_mode_and_keywords():
    p = prompts.build_prompt("Some passage.", "formal", ["ASTM A106"])
    assert "Some passage." in p
    assert "formal" in p.lower()
    assert "ASTM A106" in p


def test_variant_prompt_differs():
    a = prompts.build_prompt("x", "standard", [])
    b = prompts.build_prompt("x", "standard", [], variant=1)
    assert a != b
