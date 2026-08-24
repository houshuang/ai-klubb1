#!/usr/bin/env python3
"""Fyll seed-banken: generer oppgaver for alle kombinasjoner av tid × kategori.

Kjøres der OPENAI_API_KEY finnes (typisk på serveren):

    cd /opt/klubb1/backend && set -a && . /etc/klubb1.env && set +a
    .venv/bin/python ../scripts/seed_tasks.py --per-kombinasjon 2 --out seed_tasks.json

Resultatet committes som backend/seed_tasks.json, slik at automaten alltid har
lapper å gi – også uten API-nøkkel eller når modellen er nede.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app import openai_json  # noqa: E402
from bank import MEDIER, NIVAER, trekk  # noqa: E402
from prompts import OPPGAVE_SCHEMA, oppgave_system, oppgave_user  # noqa: E402


async def en(minutter: int, kategori: str, niva: str, gruppe: bool, rng: random.Random) -> dict | None:
    ingr = trekk(kategori, rng)
    try:
        task, _ = await openai_json(oppgave_system(), oppgave_user(minutter, niva, gruppe, ingr), OPPGAVE_SCHEMA, "oppgave")
    except Exception as exc:  # noqa: BLE001
        print(f"  ! {minutter}/{kategori}/{niva}: {exc}", file=sys.stderr)
        return None
    task.update({"minutter": minutter, "kategori": ingr["kategori"], "niva": niva, "gruppe": gruppe, "ingredienser": {k: ingr[k] for k in ("medium", "tema", "vri")}})
    print(f"  ✓ {minutter} min · {ingr['kategori']} · {niva}: {task['tittel']}")
    return task


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-kombinasjon", type=int, default=1)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "backend" / "seed_tasks.json"))
    ap.add_argument("--parallel", type=int, default=6)
    args = ap.parse_args()

    rng = random.Random(2026)
    nivaer = list(NIVAER)
    jobs = []
    for minutter in (15, 30, 60):
        for kategori in MEDIER:
            for i in range(args.per_kombinasjon):
                jobs.append((minutter, kategori, nivaer[i % len(nivaer)], i % 2 == 1))
    print(f"{len(jobs)} oppgaver å lage")

    sem = asyncio.Semaphore(args.parallel)

    async def run(job):
        async with sem:
            return await en(*job, rng)

    results = [t for t in await asyncio.gather(*(run(j) for j in jobs)) if t]
    out = Path(args.out)
    existing = []
    if out.exists():
        try:
            existing = json.loads(out.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []
    out.write_text(json.dumps(existing + results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"skrev {len(results)} nye (totalt {len(existing) + len(results)}) til {out}")


if __name__ == "__main__":
    asyncio.run(main())
