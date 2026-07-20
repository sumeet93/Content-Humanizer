# Humanizer

Free, self-hosted AI-text humanizer. Paste AI-generated text, get a rewrite
that reads like a person wrote it — with an honest local AI-likeness score,
a word-level diff of what changed, locked keywords, and no word limits.

Built as a better version of humanizeai.pro + Ahrefs' AI Humanizer:

| | humanizeai.pro | Ahrefs | **this tool** |
|---|---|---|---|
| Price | $4.99–$29.99/mo | free | **free** |
| Input limit | word credits | 2,048 chars | **none** (chunked) |
| Modes | paid tiers | none | **all free** (6 modes) |
| Keyword lock | paid | no | **yes, verified + retried** |
| Detection check | fake (always 0%) | none | **honest heuristic w/ breakdown** |
| Diff view | color-coded | none | **word-level highlighter diff** |
| Engine | small paraphrase model | in-house LM | **Claude + rule-based post-pass** |

## How it works

```
text -> chunk (900w, paragraph-aware, parallel)
     -> Claude rewrite (one compact prompt per chunk, no thinking pass)
     -> deterministic post-pass (em-dashes, AI vocabulary, contractions)  [0 tokens]
     -> keyword verification (retry only the failing chunk, once)
     -> heuristic scorer + word diff                                      [0 tokens]
```

Token use is deliberately minimal: exactly one LLM call per chunk (plus at
most one retry per chunk if a locked term was dropped). Everything else is
pure Python.

## Run locally (Claude CLI engine — free with your subscription)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app:app --port 8787
# open http://127.0.0.1:8787
```

Requires the `claude` CLI to be installed and logged in.

## Deploy on a server (OVH) — Anthropic API engine

```bash
export HUMANIZER_ENGINE=api
export ANTHROPIC_API_KEY=sk-ant-...
export HUMANIZER_MODEL=claude-opus-4-8   # or claude-sonnet-5 / claude-haiku-4-5 for cheaper
uvicorn app:app --host 0.0.0.0 --port 8787
```

Put nginx (basic auth or IP allowlist recommended for a team deployment) in
front of it. One env var switches the engine; nothing else changes.

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `HUMANIZER_ENGINE` | `claude-cli` | `claude-cli` or `api` |
| `HUMANIZER_MODEL` | `claude-opus-4-8` | model for either engine |
| `HUMANIZER_MAX_CHARS` | `120000` | per-request input cap |
| `HUMANIZER_CLI_TIMEOUT` | `240` | seconds per CLI call |

## API

- `POST /api/humanize` `{text, mode, keywords[], variants}` → rewrite(s) with diff + scores
- `POST /api/score` `{text}` → heuristic AI-likeness score with metric breakdown
- `GET /api/health` → engine info

Modes: `standard`, `formal`, `informal`, `academic`, `shorten`, `expand`.

## Tests

```bash
.venv/bin/pytest tests/ -q
```
