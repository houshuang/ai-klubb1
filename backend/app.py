"""AI-klubb1 Tivoli – API for Oppgave-automaten og Spørrespeilet.

Kjøres som `uvicorn app:app --host 127.0.0.1 --port 3005` bak nginx.
Én prosess, én SQLite-fil. Ingen samtaleinnhold fra Spørrespeilet lagres –
bare tellere. Genererte oppgaver lagres, slik at de kan vises på oppslagstavla
og gjenbrukes hvis modellen er nede.
"""

from __future__ import annotations

import json
import logging
import os
import random
import sqlite3
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, AsyncIterator, Iterator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from bank import KATEGORIER, NIVAER, trekk
from prompts import (
    OPPGAVE_SCHEMA,
    SPEIL_APNING,
    SPEIL_HINT_MARKER,
    SPEIL_MODI,
    oppgave_system,
    oppgave_user,
    speil_system,
)

log = logging.getLogger("klubb1")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

OPENAI_URL = "https://api.openai.com/v1/responses"
MODEL = os.environ.get("KLUBB1_MODEL", "gpt-5.6-luna")
DATA_DIR = Path(os.environ.get("KLUBB1_DATA_DIR", Path(__file__).parent / "data"))
DB_PATH = DATA_DIR / "klubb1.db"
SEED_PATH = Path(__file__).parent / "seed_tasks.json"
KLUBB_KODE = os.environ.get("KLUBB1_KODE", "").strip()
MAX_OPPGAVER_PER_DAG = int(os.environ.get("KLUBB1_MAX_OPPGAVER_PER_DAG", "400"))
MAX_SPEIL_PER_DAG = int(os.environ.get("KLUBB1_MAX_SPEIL_PER_DAG", "2000"))
MAX_SPEIL_TURER = 40  # meldinger per samtale som sendes videre til modellen

app = FastAPI(title="AI-klubb1 Tivoli", docs_url=None, redoc_url=None)


# --------------------------------------------------------------------------- db

def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS oppgaver (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created REAL NOT NULL,
                minutter INTEGER NOT NULL,
                kategori TEXT NOT NULL,
                niva TEXT NOT NULL,
                gruppe INTEGER NOT NULL DEFAULT 0,
                kilde TEXT NOT NULL,
                json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bruk (
                dag TEXT NOT NULL,
                hva TEXT NOT NULL,
                antall INTEGER NOT NULL DEFAULT 0,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (dag, hva)
            );
            """
        )


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def bruk_i_dag(hva: str) -> int:
    with db() as conn:
        row = conn.execute("SELECT antall FROM bruk WHERE dag=? AND hva=?", (date.today().isoformat(), hva)).fetchone()
    return int(row["antall"]) if row else 0


def registrer_bruk(hva: str, usage: dict[str, Any] | None = None) -> None:
    usage = usage or {}
    with db() as conn:
        conn.execute(
            """
            INSERT INTO bruk (dag, hva, antall, input_tokens, output_tokens) VALUES (?, ?, 1, ?, ?)
            ON CONFLICT(dag, hva) DO UPDATE SET
                antall = antall + 1,
                input_tokens = input_tokens + excluded.input_tokens,
                output_tokens = output_tokens + excluded.output_tokens
            """,
            (date.today().isoformat(), hva, int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)),
        )


# ----------------------------------------------------------------------- openai

def openai_headers() -> dict[str, str]:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Automaten mangler strøm (ingen API-nøkkel).")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


async def openai_json(system: str, user: str, schema: dict, name: str, timeout: float = 90.0) -> tuple[dict, dict]:
    payload = {
        "model": MODEL,
        "reasoning": {"effort": "low"},
        "instructions": system,
        "input": user,
        "max_output_tokens": 2500,
        "text": {"format": {"type": "json_schema", "name": name, "strict": True, "schema": schema}},
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(OPENAI_URL, headers=openai_headers(), json=payload)
    if r.status_code >= 400:
        log.error("openai %s: %s", r.status_code, r.text[:500])
        raise HTTPException(status_code=502, detail="Automaten hostet. Prøv igjen.")
    data = r.json()
    text = ""
    for item in data.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    text = c.get("text", "")
    if not text:
        raise HTTPException(status_code=502, detail="Automaten spyttet ut en tom lapp.")
    return json.loads(text), data.get("usage", {}) or {}


async def openai_stream(system: str, messages: list[dict[str, str]], timeout: float = 120.0) -> AsyncIterator[dict]:
    payload = {
        "model": MODEL,
        "reasoning": {"effort": "low"},
        "instructions": system,
        "input": messages,
        "max_output_tokens": 600,
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", OPENAI_URL, headers=openai_headers(), json=payload) as r:
            if r.status_code >= 400:
                body = await r.aread()
                log.error("openai stream %s: %s", r.status_code, body[:500])
                raise HTTPException(status_code=502, detail="Speilet dugget til. Prøv igjen.")
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw or raw == "[DONE]":
                    continue
                try:
                    yield json.loads(raw)
                except json.JSONDecodeError:
                    continue


# ------------------------------------------------------------------ oppgaver

class OppgaveRequest(BaseModel):
    minutter: int = Field(30, description="15, 30 eller 60")
    kategori: str = "overrask"
    niva: str = "vant"
    gruppe: bool = False
    onske: str = Field("", max_length=300)


def _seed_tasks() -> list[dict]:
    if not SEED_PATH.exists():
        return []
    try:
        return json.loads(SEED_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _fallback(minutter: int, kategori: str) -> dict | None:
    """Trekk en tidligere oppgave fra databasen eller seed-banken."""
    with db() as conn:
        rows = conn.execute(
            "SELECT id, json, kategori, niva, gruppe FROM oppgaver WHERE minutter=? AND (?='overrask' OR kategori=?) ORDER BY RANDOM() LIMIT 1",
            (minutter, kategori, kategori),
        ).fetchall()
    if rows:
        row = rows[0]
        task = json.loads(row["json"])
        task.update({"id": row["id"], "minutter": minutter, "kategori": row["kategori"], "niva": row["niva"], "gruppe": bool(row["gruppe"]), "kilde": "arkiv"})
        return task
    seeds = [t for t in _seed_tasks() if t.get("minutter") == minutter and (kategori == "overrask" or t.get("kategori") == kategori)]
    if seeds:
        task = dict(random.choice(seeds))
        task["kilde"] = "seed"
        return task
    return None


def _normaliser(task: dict, req: OppgaveRequest, kilde: str) -> dict:
    return {**task, "minutter": req.minutter, "kategori": req.kategori, "niva": req.niva, "gruppe": req.gruppe, "kilde": kilde}


@app.post("/api/oppgave")
async def lag_oppgave(req: OppgaveRequest) -> dict:
    if req.minutter not in (15, 30, 60):
        raise HTTPException(status_code=400, detail="Automaten kjenner bare 15, 30 og 60 minutter.")
    if req.kategori not in KATEGORIER:
        req.kategori = "overrask"
    if req.niva not in NIVAER:
        req.niva = "vant"

    ingredienser = trekk(req.kategori)
    if bruk_i_dag("oppgave") >= MAX_OPPGAVER_PER_DAG or not os.environ.get("OPENAI_API_KEY"):
        task = _fallback(req.minutter, ingredienser["kategori"])
        if task:
            return task
        raise HTTPException(status_code=503, detail="Automaten er tom for lapper i dag. Kom tilbake i morgen.")

    try:
        task, usage = await openai_json(oppgave_system(), oppgave_user(req.minutter, req.niva, req.gruppe, ingredienser, req.onske), OPPGAVE_SCHEMA, "oppgave")
    except (HTTPException, httpx.HTTPError, json.JSONDecodeError) as exc:
        log.warning("oppgave fallback: %s", exc)
        task = _fallback(req.minutter, ingredienser["kategori"])
        if task:
            return task
        raise HTTPException(status_code=502, detail="Automaten hostet og har ingen gamle lapper å gi deg. Prøv igjen.")

    registrer_bruk("oppgave", usage)
    task["ingredienser"] = {k: ingredienser[k] for k in ("medium", "tema", "vri")}
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO oppgaver (created, minutter, kategori, niva, gruppe, kilde, json) VALUES (?,?,?,?,?,?,?)",
            (time.time(), req.minutter, ingredienser["kategori"], req.niva, int(req.gruppe), "luna", json.dumps(task, ensure_ascii=False)),
        )
        task_id = cur.lastrowid
    out = _normaliser(task, req, "luna")
    out["kategori"] = ingredienser["kategori"]
    out["id"] = task_id
    return out


@app.get("/api/oppgave/{task_id}")
def hent_oppgave(task_id: int) -> dict:
    with db() as conn:
        row = conn.execute("SELECT * FROM oppgaver WHERE id=?", (task_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Ingen lapp med det nummeret.")
    task = json.loads(row["json"])
    task.update({"id": row["id"], "minutter": row["minutter"], "kategori": row["kategori"], "niva": row["niva"], "gruppe": bool(row["gruppe"]), "kilde": row["kilde"], "created": row["created"]})
    return task


@app.get("/api/oppgaver")
def liste_oppgaver(minutter: int | None = None, kategori: str | None = None, limit: int = 40) -> dict:
    limit = max(1, min(limit, 100))
    q = "SELECT id, created, minutter, kategori, niva, gruppe, json FROM oppgaver WHERE 1=1"
    args: list[Any] = []
    if minutter in (15, 30, 60):
        q += " AND minutter=?"
        args.append(minutter)
    if kategori and kategori in KATEGORIER and kategori != "overrask":
        q += " AND kategori=?"
        args.append(kategori)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with db() as conn:
        rows = conn.execute(q, args).fetchall()
    items = []
    for row in rows:
        t = json.loads(row["json"])
        items.append({
            "id": row["id"], "created": row["created"], "minutter": row["minutter"], "kategori": row["kategori"],
            "niva": row["niva"], "gruppe": bool(row["gruppe"]), "tittel": t.get("tittel"), "teaser": t.get("teaser"), "tags": t.get("tags", []),
        })
    return {"oppgaver": items}


# --------------------------------------------------------------------- speil

class SpeilMelding(BaseModel):
    role: str
    content: str = Field(..., max_length=4000)


class SpeilRequest(BaseModel):
    modus: str = "ide"
    meldinger: list[SpeilMelding] = Field(default_factory=list)
    hint: bool = False
    kode: str = ""


@app.get("/api/speil/apning")
def speil_apning(modus: str = "ide") -> dict:
    return {"modus": modus if modus in SPEIL_MODI else "ide", "tekst": SPEIL_APNING.get(modus, SPEIL_APNING["ide"])}


@app.post("/api/speil")
async def speil(req: SpeilRequest) -> StreamingResponse:
    if KLUBB_KODE and req.kode.strip().lower() != KLUBB_KODE.lower():
        raise HTTPException(status_code=401, detail="Feil klubbkode. Spør en hjelper.")
    if req.modus not in SPEIL_MODI:
        req.modus = "ide"
    if bruk_i_dag("speil") >= MAX_SPEIL_PER_DAG:
        raise HTTPException(status_code=503, detail="Speilet er sliten i dag. Kom tilbake i morgen.")
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="Speilet mangler strøm (ingen API-nøkkel).")

    messages: list[dict[str, str]] = []
    for m in req.meldinger[-MAX_SPEIL_TURER:]:
        role = "assistant" if m.role == "assistant" else "user"
        content = m.content.strip()
        if content:
            messages.append({"role": role, "content": content})
    if not messages or messages[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="Speilet trenger noe å svare på.")
    user_turns = sum(1 for m in messages if m["role"] == "user")
    if req.hint:
        if user_turns < 3:
            raise HTTPException(status_code=400, detail="Hint-spaken sitter fast til du har svart tre ganger.")
        messages[-1] = {"role": "user", "content": messages[-1]["content"] + "\n\n" + SPEIL_HINT_MARKER}

    async def gen() -> AsyncIterator[bytes]:
        usage: dict[str, Any] = {}
        try:
            async for event in openai_stream(speil_system(req.modus), messages):
                et = event.get("type", "")
                if et == "response.output_text.delta":
                    yield f"data: {json.dumps({'delta': event.get('delta', '')}, ensure_ascii=False)}\n\n".encode()
                elif et == "response.completed":
                    usage = (event.get("response") or {}).get("usage") or {}
                elif et in ("response.failed", "error"):
                    yield f"data: {json.dumps({'error': 'Speilet dugget til. Prøv igjen.'})}\n\n".encode()
        except HTTPException as exc:
            yield f"data: {json.dumps({'error': exc.detail})}\n\n".encode()
        except httpx.HTTPError as exc:
            log.warning("speil stream error: %s", exc)
            yield f"data: {json.dumps({'error': 'Speilet mistet kontakten. Prøv igjen.'})}\n\n".encode()
        finally:
            registrer_bruk("speil", usage)
        yield b"data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --------------------------------------------------------------------- misc

@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "model": MODEL,
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
        "kode_kreves": bool(KLUBB_KODE),
        "i_dag": {"oppgave": bruk_i_dag("oppgave"), "speil": bruk_i_dag("speil")},
        "tak": {"oppgave": MAX_OPPGAVER_PER_DAG, "speil": MAX_SPEIL_PER_DAG},
    }


@app.get("/api/meta")
def meta() -> dict:
    return {
        "kategorier": [{"id": k, "navn": v["navn"], "hint": v["hint"]} for k, v in KATEGORIER.items()],
        "nivaer": [{"id": k, "tekst": v} for k, v in NIVAER.items()],
        "modi": list(SPEIL_MODI.keys()),
        "kode_kreves": bool(KLUBB_KODE),
    }


@app.exception_handler(HTTPException)
async def http_exc(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


init_db()

# Lokal utvikling: `KLUBB1_SERVE_WEB=1` serverer ../web fra samme prosess.
# I produksjon serverer nginx web/ som statiske filer og proxyer bare /api/.
if os.environ.get("KLUBB1_SERVE_WEB"):
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "web", html=True), name="web")
