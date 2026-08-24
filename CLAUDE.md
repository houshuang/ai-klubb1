# Klubb1 Tivoli — dev notes

Read `README.md` first. Two attractions for AI-klubb1 (youth club, Hamar, ages 13–21),
live at `https://alifstian.duckdns.org/klubb1/`, public GitHub `houshuang/ai-klubb1`.

## Shape
- `backend/` FastAPI, one file (`app.py`), plain `httpx` to the OpenAI Responses API,
  model `gpt-5.6-luna`. `bank.py` = ingredient lists, `prompts.py` = all prompts + JSON schema.
  SQLite at `KLUBB1_DATA_DIR/klubb1.db` (tasks + daily usage counters only).
- `web/` static, no build step. `style.css` + `app.js` shared; `index.html`, `automat.html`,
  `speil.html`. API is called relatively (`api/...`) so it works under any path prefix.
- `deploy/` systemd unit, nginx snippet, rate-limit zone, env example. `deploy.sh` rsyncs.

## Rules
- Never log Spørrespeilet conversation content on the server. Minors use this.
- Keep the mirror Socratic: no answers, one question, hint gate enforced server-side.
- Everything user-facing is Norwegian bokmål. Never the words «utforske», «spennende», no emoji in
  generated content.
- Secrets only in `/etc/klubb1.env` on the server (mode 600). Nothing in the repo.
- Alif is post-containment (2026-08-24): public nginx surfaces are explicit allowlists. Do not
  widen `deploy/nginx-klubb1.conf` beyond `/klubb1/` static + `/klubb1/api/`.
- Local Python is 3.14 (no pydantic wheels); use `uv venv --python /usr/local/bin/python3.12`.

## Verify
```
KLUBB1_SERVE_WEB=1 .venv/bin/uvicorn app:app --port 3005   # in backend/
curl -s localhost:3005/api/health
./deploy.sh && curl -fsS https://alifstian.duckdns.org/klubb1/api/health
```
