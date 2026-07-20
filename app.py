"""Humanizer — free local AI-text humanizer.

Run:  uvicorn app:app --host 127.0.0.1 --port 8787
  or: python app.py
"""
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import engine
from core import pipeline, scorer

app = FastAPI(title="Humanizer")

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

MAX_INPUT_CHARS = int(os.environ.get("HUMANIZER_MAX_CHARS", "120000"))


class HumanizeRequest(BaseModel):
    text: str = Field(min_length=1)
    mode: str = "standard"
    keywords: list[str] = []
    variants: int = 1


class ScoreRequest(BaseModel):
    text: str = Field(min_length=1)


@app.get("/api/health")
async def health():
    return {"ok": True, **engine.info()}


@app.post("/api/score")
async def api_score(req: ScoreRequest):
    return scorer.score(req.text)


@app.post("/api/humanize")
async def api_humanize(req: HumanizeRequest):
    if len(req.text) > MAX_INPUT_CHARS:
        raise HTTPException(413, f"Input over {MAX_INPUT_CHARS} characters; split it up.")
    keywords = [k.strip() for k in req.keywords if k.strip()][:20]
    try:
        return await pipeline.humanize(req.text, req.mode, keywords, req.variants)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except engine.EngineError as e:
        raise HTTPException(502, str(e))


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8787")))
