# Medical AI Assistant

HRV(심박변이도) 연구 참가자용 챗봇입니다. Streamlit UI가 FastAPI로 질문을 보내고, LangChain **tool-calling agent**가 개인 HRV(SQL)와 업로드된 논문(RAG) 중 필요한 도구만 고릅니다.

자세한 구조는 [docs/architecture.md](docs/architecture.md), 요청 경로는 [docs/data-flow.md](docs/data-flow.md)를 보세요.

---

## Architecture (요약)

```
Browser → Streamlit (:8501) → FastAPI (:8000) → Agent (Groq)
                                    ├─ query_hrv_data      → Supabase PostgreSQL
                                    └─ search_research_docs → Pinecone
```

- **라우팅:** 키워드 분류기가 아니라 LLM + tool docstring
- **DB:** 호스팅된 Supabase (로컬 Postgres 컨테이너 없음)
- **관측:** LangSmith (`ask` vs `eval_*` 태그)
- **평가:** `server/eval/` 18문항 golden set (routing / SQL / RAGAS / safety)

---

## Prerequisites

- Python **3.12+**
- [uv](https://docs.astral.sh/uv/)
- 계정·키: **Supabase** (`DATABASE_URL`), **Groq**, **Google** (임베딩), **Pinecone**
- 선택: **LangSmith** (트레이싱), **Docker Desktop** (`compose up`)

---

## Local setup

저장소 루트에서:

```bash
uv sync
cp .env.example server/.env
```

`server/.env`에 실제 키를 채우세요. **`.env`는 커밋하지 마세요.** (`.gitignore`에 `.env`, `**/.env`)

Windows PowerShell:

```powershell
uv sync
Copy-Item .env.example server\.env
```

플레이스홀더 목록은 [`.env.example`](.env.example)과 같습니다. 앱이 읽는 파일은 **`server/.env`** 입니다.

첫 실행 전에 Streamlit에서 참가자 CSV와 연구 PDF를 올리면 SQL·RAG가 의미 있는 답을 냅니다. 평가용 고정 참가자는 `EVAL_P001` 픽스처입니다 (아래 Evaluation).

---

## Run

한 번에 **하나만** 쓰세요. `:8000` / `:8501`을 겹치게 켜면 포트가 충돌합니다.

### 1. Local (개발)

터미널 1 — API (`server/`가 cwd여야 `from modules...`가 동작합니다):

```bash
cd server
uv run --project .. uvicorn main:app --host 0.0.0.0 --port 8000
```

터미널 2 — UI:

```bash
cd client
uv run --project .. streamlit run app.py
```

- UI: http://localhost:8501
- API docs: http://localhost:8000/docs
- DB 헬스: http://localhost:8000/health/db

`client/config.py`는 `BACKEND_URL`이 없으면 `http://127.0.0.1:8000`을 씁니다.

### 2. Docker Compose (재현)

Docker Desktop을 켠 뒤, 로컬 uvicorn/streamlit은 끄고 저장소 루트에서:

```bash
docker compose up --build
```

이미지가 있으면 `docker compose up`만으로 됩니다. compose가 `server/.env`를 서버 컨테이너에 주입하고, Streamlit에는 `BACKEND_URL=http://server:8000`을 넣습니다. Postgres는 컨테이너로 올리지 않습니다.

끄기: `Ctrl+C` 또는 `docker compose down`.

라이브 리로드가 필요하면 [`docker-compose.override.example.yml`](docker-compose.override.example.yml)을 `docker-compose.override.yml`로 복사하세요 (gitignore).

---

## Evaluation

채팅 UI(Streamlit)와 **별개**입니다. 18문항을 Agent에 넣고 routing / SQL / RAGAS / LLM-judge(safety 포함)를 채점합니다. Docker compose를 켜 둘 필요는 없습니다.

저장소 루트, `.venv`에서 (`server/.env` 필요):

```bash
# 전체 18문항
uv run python -m server.eval.runners.baseline_runner --run-name baseline_v1

# 프롬프트 개선 후 재평가
uv run python -m server.eval.runners.baseline_runner --run-name improved_v1

# 두 런 비교
uv run python -m server.eval.compare \
  --baseline server/eval/results/baseline_v1_<timestamp> \
  --candidate server/eval/results/improved_v1_<timestamp>

# 실패 유형 리포트
uv run python -m server.eval.analysis.failure_report \
  --run-dir server/eval/results/improved_v1_<timestamp>
```

기본값: `--seed-db` 로 `EVAL_P001`을 픽스처 CSV에서 다시 넣습니다. 결과는 `server/eval/results/<run_id>/` (`summary.csv`, `details.jsonl`, `metadata.json`). 이 폴더는 gitignore입니다.

데이터셋 설명: [`server/eval/datasets/README.md`](server/eval/datasets/README.md).  
SQL expected는 프로덕션 핸들러와 **다른 스크립트**로 계산합니다 (`server/eval/ground_truth/compute_sql_truth.py`).

스모크 (RAGAS·judge 생략):

```bash
uv run python -m server.eval.runners.baseline_runner --run-name smoke --skip-ragas --skip-judge --limit 2
```

---

## LangSmith tracing

Agent 호출이 대시보드에 남습니다. Streamlit은 HTTP만 보내고, 트레이스는 **FastAPI(또는 eval 러너)** 가 남깁니다.

`server/.env` (또는 Render 등 호스트 env):

```
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=medical-ai-assistant
```

키가 없으면 서버는 경고만 하고 기동합니다.

| 경로 | 태그 |
|------|------|
| `POST /ask/` | `ask` |
| eval 러너 | `eval`, `eval_<run_id>`, `eval_007` 등 |

RAGAS / judge LLM은 대시보드가 안 섞이게 tracing에서 빼 둡니다. 대시보드: https://smith.langchain.com

로컬·Docker·Render 모두 같은 프로젝트에 쌓일 수 있으니 태그로 필터하세요.

---

## API endpoints

| Method | Path | 역할 |
|--------|------|------|
| `GET` | `/health/db` | Supabase 연결 + `participants` / `hrv_readings` 존재 |
| `POST` | `/upload_pdfs/` | PDF 저장 후 Pinecone 인덱싱 |
| `POST` | `/upload_csv/` | HRV CSV → 참가자 코드 기준 적재 (`participant_code`) |
| `POST` | `/ask/` | Agent. form: `question`, `participant_code` (기본 `P001`) |

`/ask/` 응답: `response`, `sources`, `tools_used`.

---

## Resume highlights

동일 18문항 (`mvp_eval.jsonl`), 프롬프트·tool docstring만 수정한 뒤:

| Metric | baseline_v1 | improved_v1 |
|--------|-------------|-------------|
| Routing exact match | 1.00 | 1.00 |
| SQL pass rate | 1.00 | 1.00 |
| RAG faithfulness (mean) | 0.38 | **0.58** |
| Safety pass rate | 0.50 | **1.00** |
| Judge overall (mean) | 4.67 | 4.67 |
| Examples with ≥1 failure | 7 | **5** |

- Tool-calling agent: `query_hrv_data` (90일 lookback) + `search_research_docs`
- 4영역 eval + LangSmith + `failure_report` → 최소 프롬프트 수정 (`server/eval/improvements/CHANGELOG.md`)
- Docker Compose로 API+UI 재현, DB는 Supabase

한계: 18문항 golden set이라 프롬프트 overfitting 위험이 있습니다. relevancy는 보수적 RAG 호출 때문에 일부 하락했습니다.

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
