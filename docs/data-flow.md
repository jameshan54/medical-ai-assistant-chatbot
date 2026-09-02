# Data flow

How requests move through storage, the agent, and the eval pipeline. Component list: [architecture.md](architecture.md).

---

## PDF ingest (RAG)

```mermaid
flowchart LR
    U[Streamlit upload] -->|multipart files| API["POST /upload_pdfs/"]
    API --> SAVE[pdf_handlers.save_uploaded_files]
    SAVE --> VS[load_vectorstore]
    VS --> EMB[Google embeddings]
    EMB --> PC[(Pinecone index)]
```

1. The client posts PDFs to `POST /upload_pdfs/`.
2. The server saves them locally, splits text, and embeds.
3. Chunks land in Pinecone. Later, `search_research_docs(query)` searches that index.

---

## CSV ingest (SQL)

```mermaid
flowchart LR
    U[Streamlit CSV] -->|file + participant_code| API["POST /upload_csv/"]
    API --> H[csv_handlers.save_hrv_csv]
    H --> PG[(Supabase participants / hrv_readings)]
```

1. A CSV is uploaded with `participant_code` (default `P001`).
2. Rows are written to PostgreSQL `hrv_readings`.
3. The agent's `query_hrv_data` aggregates the **last 90 days** only (`days=90`).

Eval participant `EVAL_P001` is loaded from `server/eval/fixtures/seed_hrv.csv` via `seed_db.py`, not from the UI.

---

## Ask (production)

```mermaid
flowchart TB
    Q[User question] --> ST[Streamlit]
    ST -->|BACKEND_URL /ask/| ASK[ask_question]
    ASK --> AG[run_hrv_agent]
    AG --> LLM[Groq tool loop]
    LLM -->|optional| SQL[query_hrv_data]
    LLM -->|optional| RAG[search_research_docs]
    SQL --> PG[(Supabase)]
    RAG --> PC[(Pinecone)]
    AG --> LS[LangSmith tag ask]
    AG --> OUT[response + sources + tools_used]
    OUT --> ST
```

- Local: no `BACKEND_URL` → `http://127.0.0.1:8000`
- Docker: `BACKEND_URL=http://server:8000` (Compose service name)
- Symptom, medication, or emergency cues should skip tools and use the safety redirect.
- Unrelated non-medical questions (weather, coding) skip tools and stay in the HRV-only fallback. Eval treats **safety** and **out_of_scope** as different categories.

---

## Eval pipeline

```mermaid
flowchart LR
    subgraph evalFlow [Eval Pipeline]
        DS[mvp_eval.jsonl]
        SEED[seed EVAL_P001]
        RUN[baseline_runner]
        M1[routing]
        M2[sql_det]
        M3[ragas]
        M4[llm_judge]
        OUT[results/run_id]
        DS --> RUN
        SEED --> RUN
        RUN --> M1
        RUN --> M2
        RUN --> M3
        RUN --> M4
        M1 --> OUT
        M2 --> OUT
        M3 --> OUT
        M4 --> OUT
    end
```

1. `--seed-db` (default) reseeds `EVAL_P001` from the fixture.
2. Each `EvalExample` line runs through `run_eval_example` → `run_hrv_agent(..., capture_trace=True)`.
3. Four metric areas are scored into `details.jsonl` / `summary.csv` / `metadata.json` (git commit, models, LangSmith tag).
4. `compare.py` writes baseline vs candidate deltas.
5. `failure_report.py` groups failure types and adds LangSmith filter hints.

Asking questions in Streamlit does not write these CSVs.

---

## SQL ground truth vs actual

Gold numbers and the live query use different code so scoring cannot be circular.

```mermaid
flowchart TB
    CSV[fixtures/seed_hrv.csv]
    CSV --> GT[compute_sql_truth.py]
    GT --> EXP[ground_truth/sql_expected.json]
    EXP --> MET[metrics/sql.py]

    ASK[Agent query_hrv_data]
    ASK --> PR[sql_handlers.build_sql_result]
    PR --> PG[(Supabase EVAL_P001)]
    PR --> TR[TraceCollector.sql_result]
    TR --> MET
    MET --> PASS[sql passed / fail]
```

- **Expected:** independent script over the CSV + reference date + lookback. It does not import production SQL modules.
- **Actual:** runtime `build_sql_result` only. Eval compares the traced numbers to expected.

Production lookback is 90 days; the fixture span is about 30 days. `expected_date_range_days` is the **tool lookback**, not the fixture window.

---

## Docker deploy

```mermaid
flowchart LR
    subgraph host [Developer machine]
        DC[docker compose up]
        ENV[server/.env]
    end
    subgraph boxes [Containers]
        S[server :8000]
        C[client :8501]
    end
    subgraph ext [External]
        SB[(Supabase)]
        PN[Pinecone]
        GR[Groq]
        L[LangSmith]
    end
    DC --> S
    DC --> C
    ENV --> S
    C -->|http://server:8000| S
    S --> SB
    S --> PN
    S --> GR
    S --> L
```

1. Images: `Dockerfile.server` (uv + `pyproject.toml`), `Dockerfile.client` (Streamlit).
2. `.dockerignore` keeps `.env`, `.venv`, and eval results out of the image. Keys enter only via runtime `env_file`.
3. Browser → `:8501` → `server:8000` on the Compose network → cloud DB/LLM.

Local development can skip Compose and use uvicorn + Streamlit. The eval runner is not in the image CMD; run it from the host `.venv`.
