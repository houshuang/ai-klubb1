# Klubb1 Tivoli

To attraksjoner for [AI-klubb1](https://aiklubb1.no) – Hamars gratis ungdomsklubb (13–21 år) for
kreativitet med AI. Laget som et lite tivoli i penn-og-blekk, ca. 1904.

**Live:** https://alifstian.duckdns.org/klubb1/

| Attraksjon | Hva | Side |
|---|---|---|
| **Oppgave-automaten** | Velg 15 / 30 / 60 minutter, kategori og nivå, dra i spaken. Ut kommer en lapp med én oppgave som lærer ett nytt AI-grep og ender i noe som kan vises fram. | `web/automat.html` |
| **Spørrespeilet** | Sokratisk samtalepartner à la Estlands «Iti» (TI-Hüpe): gir aldri svar, stiller ett spørsmål om gangen, gir tilbakemelding på tenkingen. Hint-spak låses opp etter tre svar. | `web/speil.html` |
| Oppslagstavla | De siste lappene automaten har laget, med delbare lenker. | `web/index.html` |

## Hvordan oppgavene blir til

Språkmodeller lager nesten alltid den samme oppgaven hvis du bare spør. Derfor trekker automaten
først tilfeldige **ingredienser** fra [`backend/bank.py`](backend/bank.py):

```
medium (per kategori)  ×  2 temaer  ×  1 vri  ×  2 AI-grep  ×  vis-fram-måte
```

…og gir dem til modellen (`gpt-5.6-luna` via OpenAI Responses API, strukturert JSON-utdata) sammen
med tid, nivå og alene/gruppe. Prompten ligger i [`backend/prompts.py`](backend/prompts.py). Hver
lapp har: tittel, teaser, oppdrag, steg med tid (første steg er alltid uten AI), *AI-grepet*, 2–4
alternative verktøy (minst ett gratis), hint hvis du står fast, vis fram, bonus, og en skjult
seksjon *Til hjelperen* for de voksne.

Vil du ha andre oppgaver? Legg til linjer i `bank.py`. Det er hele poenget med at koden er åpen.

Fallback i tre lag: modell → tidligere lapper i databasen → `backend/seed_tasks.json`. Automaten
virker altså også uten API-nøkkel.

## Spørrespeilet

Reglene står i `SPEIL_SYSTEM` i `prompts.py`. Kort: aldri svar, ett spørsmål, maks tre setninger,
tilbakemelding på tenkingen etter hvert svar, be om oppsummering med egne ord til slutt. Fire modi:
*Jeg har en idé · Jeg står fast · Jeg vil forstå noe · Utfordre meg*.

Samtalen lagres bare i nettleseren (`localStorage`). Serveren logger ikke innhold, bare antall
meldinger og tokens per dag. Hint-spaken håndheves på serveren (400 før tre brukersvar).

Hvis `KLUBB1_KODE` er satt, må man skrive inn klubbkoden én gang før speilet svarer.

## Kjøre lokalt

```bash
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
OPENAI_API_KEY=sk-... KLUBB1_SERVE_WEB=1 .venv/bin/uvicorn app:app --port 3005 --reload
open http://localhost:3005/
```

Uten `OPENAI_API_KEY` svarer automaten fra seed-banken og speilet sier at det mangler strøm.

## Deploy (Alif)

```bash
./deploy.sh              # sync + restart + health
./deploy.sh --install    # første gang: systemd + nginx-fragmenter
```

Trenger `/etc/klubb1.env` på serveren (se `deploy/klubb1.env.example`). Nginx-fragmentet
(`deploy/nginx-klubb1.conf`) er bevisst smalt: statiske filer + `/klubb1/api/` med 120 req/min per IP (en klubbkveld sitter bak én NAT-adresse),
64 kB body, kun GET/POST. Daglige tak (`KLUBB1_MAX_*`) stopper regningen hvis noe løper løpsk.

Fyll seed-banken på serveren:

```bash
ssh alif 'cd /opt/klubb1/backend && set -a && . /etc/klubb1.env && set +a && .venv/bin/python ../scripts/seed_tasks.py --per-kombinasjon 2'
scp alif:/opt/klubb1/backend/seed_tasks.json backend/seed_tasks.json   # og commit
```

## Flytte til klubbens egen plattform

Alt som trengs er en Linux-boks med Python 3.12, nginx og en OpenAI-nøkkel. Bytt `alif` i
`deploy.sh`, endre `server_name`, og sett klubbens nøkkel i `/etc/klubb1.env`. Kostnad ved
Luna-pris ($1/M inn, $6/M ut): en lapp ≈ 8 øre (målt: ~1 600 tokens inn, ~1 000 ut), en speil-melding
≈ 1 øre. En kveld med 30 ungdommer koster noen kroner. Dagstakene (`KLUBB1_MAX_*`) gir et worst case på
rundt 50 kr/dag selv om noen misbruker det.

## Kreditering

Idé: Lage Thune Myrberget (AI-klubb1 / Foreningen Mjøsvasen). Kode: Stian Håklev, bygget med
Claude Code. Speilet er inspirert av Estlands nasjonale AI-veileder, som elevene der kaller
«tüütu» – masete – og som virker nettopp derfor. MIT-lisens.
