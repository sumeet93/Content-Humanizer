"""Pluggable rewrite engine.

HUMANIZER_ENGINE=claude-cli  (default) -> shells out to the local `claude` CLI,
    free with a Claude subscription. Used for local development.
HUMANIZER_ENGINE=api                   -> Anthropic API via the official SDK.
    Used on the OVH deployment; needs ANTHROPIC_API_KEY.

Token hygiene: one call per chunk, no thinking pass for rewrites, and
max_tokens is sized from the input instead of a blanket ceiling.
"""
import asyncio
import os


class EngineError(Exception):
    pass


ENGINE = os.environ.get("HUMANIZER_ENGINE", "claude-cli")
# Sonnet is the default: rewriting isn't intelligence-limited, and it costs
# 40% less than Opus per token (and burns CLI subscription quota slower).
MODEL = os.environ.get("HUMANIZER_MODEL", "claude-sonnet-5")
_CLI_TIMEOUT = int(os.environ.get("HUMANIZER_CLI_TIMEOUT", "240"))

# Each `claude --print` call carries ~20K tokens of harness overhead
# (measured: 15K cache-read + 5.3K cache-write), so the CLI engine uses
# large chunks to make fewer calls. The API engine has no such overhead
# and uses smaller chunks for parallelism.
CHUNK_WORDS = 900 if ENGINE == "api" else 2200

_api_client = None


def _max_tokens_for(prompt: str) -> int:
    # Rewrites are ~1:1 with input; allow 2.2x word count (expand mode grows
    # text) plus headroom, clamped so a huge chunk can't request the moon.
    words = len(prompt.split())
    return max(1024, min(int(words * 2.2) + 300, 8000))


async def _rewrite_cli(prompt: str) -> str:
    # CLAUDECODE must be unset for nested `claude` invocations (see project notes)
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    proc = await asyncio.create_subprocess_exec(
        "claude", "--print", "--model", MODEL,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        out, err = await asyncio.wait_for(
            proc.communicate(prompt.encode()), timeout=_CLI_TIMEOUT
        )
    except asyncio.TimeoutError:
        proc.kill()
        raise EngineError(f"claude CLI timed out after {_CLI_TIMEOUT}s")
    if proc.returncode != 0:
        raise EngineError(f"claude CLI failed: {err.decode()[:400]}")
    text = out.decode().strip()
    if not text:
        raise EngineError("claude CLI returned empty output")
    return text


async def _rewrite_api(prompt: str) -> str:
    global _api_client
    if _api_client is None:
        from anthropic import AsyncAnthropic
        _api_client = AsyncAnthropic()
    import anthropic
    try:
        resp = await _api_client.messages.create(
            model=MODEL,
            max_tokens=_max_tokens_for(prompt),
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.RateLimitError:
        raise EngineError("Rate limited by the Anthropic API. Try again in a minute.")
    except anthropic.APIStatusError as e:
        raise EngineError(f"Anthropic API error {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        raise EngineError("Could not reach the Anthropic API.")
    if resp.stop_reason == "refusal":
        raise EngineError("The model declined to rewrite this text.")
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    if not text:
        raise EngineError("The API returned empty output.")
    return text


async def rewrite(prompt: str) -> str:
    if ENGINE == "api":
        return await _rewrite_api(prompt)
    return await _rewrite_cli(prompt)


def info() -> dict:
    return {"engine": ENGINE, "model": MODEL}
