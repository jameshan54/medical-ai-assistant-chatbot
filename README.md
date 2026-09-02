# Medical AI Assistant

Chatbot for HRV (heart rate variability) study participants. A Streamlit UI sends questions to FastAPI. A LangChain **tool-calling agent** uses personal HRV data (SQL) and uploaded papers (RAG) only when needed.

See [docs/architecture.md](docs/architecture.md) for the system design and [docs/data-flow.md](docs/data-flow.md) for request paths.

---

## Architecture (overview)

```
Browser → Streamlit (:8501) → FastAPI (:8000) → Agent (Groq)
                                    ├─ query_hrv_data      → Supabase PostgreSQL
                                    └─ search_research_docs → Pinecone
```

- **Routing:** LLM + tool docstrings (not a keyword classifier)
- **Database:** hosted Supabase (no local Postgres container)
- **Observability:** LangSmith (`ask` vs `eval_*` tags)
- **Evaluation:** 18-item golden set in `server/eval/` (routing / SQL / RAGAS / safety)

---

## Prerequisites

- Python **3.12+**
- [uv](https://docs.astral.sh/uv/)
- Accounts and keys: **Supabase** (`DATABASE_URL`), **Groq**, **Google** (embeddings), **Pinecone**
- Optional: **LangSmith** (tracing), **Docker Desktop** (`compose up`)

---

## Local setup

From the repository root:

```bash
uv sync
cp .env.example server/.env
```

Fill in real keys in `server/.env`. **Do not commit `.env`.** (`.gitignore` covers `.env` and `**/.env`.)

Windows PowerShell:

```powershell
uv sync
Copy-Item .env.example server\.env
```

Placeholder names match [`.env.example`](.env.example). The app reads **`server/.env`**.

Upload a participant CSV and research PDFs in Streamlit so SQL and RAG have data to use. The eval fixture participant is `EVAL_P001` (see Evaluation).

---

## Run

Use **one** of these at a time. Do not bind `:8000` / `:8501` twice.

### 1. Local (development)

Terminal 1 — API (`server/` must be the cwd so `from modules...` resolves):

```bash
cd server
uv run --project .. uvicorn main:app --host 0.0.0.0 --port 8000
```

Terminal 2 — UI:

```bash
cd client
uv run --project .. streamlit run app.py
```

- UI: http://localhost:8501
- API docs: http://localhost:8000/docs
- DB health: http://localhost:8000/health/db

`client/config.py` uses `http://127.0.0.1:8000` unless `BACKEND_URL` is set.

### 2. Docker Compose (reproducible run)

Start Docker Desktop, stop local uvicorn/streamlit, then from the repo root:

```bash
docker compose up --build
```

After the first build, `docker compose up` is enough. Compose injects `server/.env` into the API container and sets `BACKEND_URL=http://server:8000` on Streamlit. Postgres is not containerized.

Stop with `Ctrl+C` or `docker compose down`.

For live reload, copy [`docker-compose.override.example.yml`](docker-compose.override.example.yml) to `docker-compose.override.yml` (gitignored).

---

## Evaluation

Separate from the Streamlit chat UI. The runner scores 18 items on routing, SQL, RAGAS, and an LLM judge (including safety). Docker Compose does not need to be running.

From the repo root, with `.venv` and `server/.env`:

```bash
# full 18-item run
uv run python -m server.eval.runners.baseline_runner --run-name baseline_v1

# re-run after prompt changes
uv run python -m server.eval.runners.baseline_runner --run-name improved_v1

# compare two runs
uv run python -m server.eval.compare \
  --baseline server/eval/results/baseline_v1_<timestamp> \
  --candidate server/eval/results/improved_v1_<timestamp>

# failure-type report
uv run python -m server.eval.analysis.failure_report \
  --run-dir server/eval/results/improved_v1_<timestamp>
```

`--seed-db` (default) reseeds `EVAL_P001` from the fixture CSV. Outputs go to `server/eval/results/<run_id>/` (`summary.csv`, `details.jsonl`, `metadata.json`). That directory is gitignored.

Dataset notes: [`server/eval/datasets/README.md`](server/eval/datasets/README.md).  
SQL expected values are computed by a script that does **not** import production SQL handlers (`server/eval/ground_truth/compute_sql_truth.py`). Prompt-change notes: [`server/eval/improvements/CHANGELOG.md`](server/eval/improvements/CHANGELOG.md).

Smoke (skip RAGAS and judge):

```bash
uv run python -m server.eval.runners.baseline_runner --run-name smoke --skip-ragas --skip-judge --limit 2
```

---

## LangSmith tracing

Agent calls show up in the dashboard. Streamlit only sends HTTP; traces come from **FastAPI** (or the eval runner).

In `server/.env` (or host env such as Render):

```
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=medical-ai-assistant
```

If the key is missing, the server logs a warning and still starts.

| Path | Tags |
|------|------|
| `POST /ask/` | `ask` |
| eval runner | `eval`, `eval_<run_id>`, `eval_007`, … |

RAGAS / judge LLM calls are excluded from tracing so they do not clutter the dashboard. Dashboard: https://smith.langchain.com

Local, Docker, and Render can share the same project — filter by tag.

---

## API endpoints

| Method | Path | Role |
|--------|------|------|
| `GET` | `/health/db` | Supabase connectivity + `participants` / `hrv_readings` |
| `POST` | `/upload_pdfs/` | Save PDFs and index in Pinecone |
| `POST` | `/upload_csv/` | Load HRV CSV for `participant_code` |
| `POST` | `/ask/` | Agent. form: `question`, `participant_code` (default `P001`) |

`/ask/` response: `response`, `sources`, `tools_used`.

---

## Project layout

```
client/                 Streamlit
server/                 FastAPI, agent, eval
  eval/                 dataset, metrics, runners, results (local)
  modules/hrv_agent.py  production agent
Dockerfile.server
Dockerfile.client
docker-compose.yml
```
