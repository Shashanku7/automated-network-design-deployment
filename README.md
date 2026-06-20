# NetOrch — AI-Powered Network Design & Deployment

AI-powered dashboard for designing and deploying enterprise-grade networks via natural language. Built for the **HPE CPP** initiative.

## Architecture

```
[Frontend :5173] ←─WS/REST── [Gateway :8080] ←─Kafka── [AI Service :8000]
                                 │                           │
                                 ├── PostgreSQL :5433        ├── Qdrant (vector store)
                                 └── Kafka :9092             ├── Ollama (LLM)
                                                             ├── Firecrawl (web search)
                                                             ├──→ [Image Gen :8001] → Kroki.io
                                                             └──→ [Topology Gatekeeper :8002]
```

## Services & Ports

| Service | Port | Tech | Description |
|---------|------|------|-------------|
| Frontend | 5173 | React 19, Vite 8 | 7-step design pipeline SPA |
| AI Service | 8000 | Python 3.14+, FastAPI | Multi-agent LLM orchestrator (5 agents) |
| Image Gen | 8001 | Python, FastAPI | D2 → SVG topology diagram rendering |
| Topology Gatekeeper | 8002 | Python, FastAPI | 4-layer JSON validation |
| Gateway | 8080 | Java 25, Quarkus | WebSocket ↔ Kafka bridge, REST API |
| Kafka | 9092 | Apache Kafka | Async message bus |
| PostgreSQL | 5433 | PostgreSQL 15+ | Conversations, tasks, events |

## Prerequisites

- **Java 25+** — Gateway
- **Python 3.14+** — AI Service, Image Gen, Gatekeeper
- **Node.js 22+** — Frontend
- **PostgreSQL 15+** — Database (port 5433)
- **Kafka** — Message broker (via Docker)
- **Ollama** — LLM host (`gemma4:31b-cloud` + `qwen3-coder:480b-cloud`)
- **Qdrant** — Vector store (cloud or local)

## Quick Start

### 1. Infrastructure

```bash
# Kafka (via Docker)
docker compose up -d

# PostgreSQL — create database and run schema
createdb -p 5433 network_design
psql -p 5433 -d network_design -f db.sql
```

### 2. AI Service

```bash
cd ai-service
cp .env.example .env    # configure Qdrant, Ollama, API keys
uv venv && uv pip install
uv run uvicorn webapp.app:app --port 8000
```

### 3. Image Generation

```bash
cd Image_generation_service
pip install -r requirements.txt
python app.py                     # port 8001
```

### 4. Topology Gatekeeper

```bash
cd topology_generation
pip install -r requirements.txt
uvicorn app:app --port 8002
```

### 5. Gateway

```bash
cd gateway
./mvnw quarkus:dev -Dquarkus.http.port=8080
```

### 6. Frontend

```bash
cd frontend/code
npm install
npm run dev                       # port 5173
```

### Unified Launcher

```bash
./start.sh                        # start all services
./start.sh --no-frontend          # skip frontend
./start.sh --stop                 # stop all services
```

## Data Ingestion

Populate the Qdrant knowledge base with HPE Aruba datasheets:

```bash
cd ai-service
python ingest.py datasheets        # equipment datasheets
python ingest.py config_guides     # configuration guides
python ingest.py all               # both
```

## Project Structure

```
ai-service/              Multi-agent LLM orchestrator (5 agents, RAG)
  webapp/                FastAPI app, routes, agents, tools, Kafka handler
  config.py              Shared config + sparse vector logic
  ingest.py              PDF → Qdrant ingestion pipeline
data/                    HPE Aruba CX datasheet PDFs
config_guides/           Network configuration guide PDFs

frontend/
  code/                  React SPA (Vite, Tailwind, React Router, ReactFlow)
  DOCUMENTATION.md       UI/UX docs

gateway/                 Java/Quarkus API gateway
  src/main/java/...      REST + WS endpoints, Kafka bridge, entities

Image_generation_service/ D2 → SVG diagram renderer
topology_generation/     JSON validation gatekeeper
schemas/                 Shared JSON Schemas (WS protocol, Kafka events)
ref_docs/                Design reference documents (PDF, diagrams)
db.sql                   PostgreSQL schema
docker-compose.yml       Kafka only
start.sh                 Unified launcher script
tasks.md                 Project task list
contributions.md         Contributor breakdown
```

## Docs per Service

| Service | Doc |
|---------|-----|
| AI Service | [`ai-service/README.md`](ai-service/README.md) |
| Frontend | [`frontend/README.md`](frontend/README.md) |
| Gateway | [`gateway/README.md`](gateway/README.md) |
| Image Gen | [`Image_generation_service/README.md`](Image_generation_service/README.md) |
| Topology Gatekeeper | [`topology_generation/README.md`](topology_generation/README.md) |
| Schemas | [`schemas/README.md`](schemas/README.md) |
| Ref Docs | [`ref_docs/README.md`](ref_docs/README.md) |
| Backend Startup | [`start_backend.md`](start_backend.md) |
| Frontend UX | [`frontend/DOCUMENTATION.md`](frontend/DOCUMENTATION.md) |
