"""Word-level diff between source and rewrite, for the 'show changes' view."""
import difflib
import re

_TOKEN = re.compile(r"\S+|\s+")


def diff_segments(original: str, rewritten: str) -> list[dict]:
    a = _TOKEN.findall(original)
    b = _TOKEN.findall(rewritten)
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    segments: list[dict] = []

    def push(text: str, changed: bool):
        if not text:
            return
        if segments and segments[-1]["changed"] == changed:
            segments[-1]["text"] += text
        else:
            segments.append({"text": text, "changed": changed})

    for op, _i1, _i2, j1, j2 in matcher.get_opcodes():
        chunk = "".join(b[j1:j2])
        if op == "equal":
            push(chunk, False)
        elif op in ("replace", "insert"):
            push(chunk, True)
        # 'delete' has nothing on the rewrite side to show
    return segments
