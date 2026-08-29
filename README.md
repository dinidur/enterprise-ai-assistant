# Enterprise AI Assistant

An enterprise knowledge assistant built on a multi-agent LangGraph orchestration
layer, hybrid retrieval over Pinecone, role-based access control and full
LangSmith observability.

> Status: **Step 1 - skeleton.** Sections below are filled in as each step lands.

---

## Architecture

_TODO: Mermaid diagram - Streamlit UI -> FastAPI -> LangGraph supervisor ->
{retrieval, research, tool} agents -> validation -> response._

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
copy .env.example .env        # Windows  (cp on macOS / Linux)
```

Fill in `.env`, then run the API:

```bash
uvicorn app.api.main:app --reload
```

Check <http://localhost:8000/health>.

## Model Selection Rationale

_TODO: which LLM, why, cost / latency / quality trade-off, fallback model._

## Retrieval Design

_TODO: chunking strategy, dense + BM25, fusion method, metadata filters._

## Recursive Language Model (RLM)

_TODO: search-plan generation, task decomposition, batched sub-agents,
aggregation, recursion depth cap._

## Memory Design

_TODO: what is kept per turn, summarisation policy, session lifetime._

## Security Approach

_TODO: prompt injection defence, input validation, guardrails, citation
verification._

## RBAC

| Role | Chat | Search | Analytics | MCP tools | Admin tools |
|---|---|---|---|---|---|
| Viewer | yes | yes | no | no | no |
| Analyst | yes | yes | yes | yes | no |
| Administrator | yes | yes | yes | yes | yes |

## Observability

_TODO: LangSmith project, what is traced, how to read a trace._

## Assumptions and Trade-offs

_TODO: every shortcut taken and why._
