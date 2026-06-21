# Code Contributions

This document lists the contributors and their core areas of contribution to the NetOrch repository.

## Contributors

- **Shashank U**
- **Shashank Shantharam Nayak**
- **Priyam Sarkar**
- **Fazal Ali Sheikh**
- **Tummala Gowtham Jignas**

## Key Contributions by Directory

### `frontend/code/`

- **Architecture**: Scaffolding of the React application using Vite 8.
- **UI Components**: Implementation of core layout components including `Sidebar`, `TopBar`, and `AppLayout`. **State Management**: Implementation of `ProjectContext` for global application state.
- **Feature Pages**:
  - **Dashboard**: Project overview and metrics.
  - **Requirements**: Natural language input interface with structured building/department breakdown.
  - **Solution Type**: Logic for selecting between campus and datacenter solutions.
  - **Proposed Design**: Streaming AI phase results with approval/revision workflow.
  - **Bill of Materials (BOM)**: Automated equipment lists from Phase 3.
  - **Detailed Topology**: Technical port mapping and configuration guides.
  - **Interactive Topology**: ReactFlow diagram rendered via SandpackViewer.
  - **Deployment**: Progress tracking for network deployment.
- **Services**: `api.js` WebSocket + REST integration layer for Gateway and AI services.

### `ai-service/webapp/`

- **FastAPI Server**: Multi-agent LLM orchestrator with Kafka-driven task processing.
- **5-Agent Workflow**: Reformer → Topology Designer → Device Selector → React Topology Architect → CLI Config Generator.
- **Kafka Integration**: Async consumer/producer for `agent-tasks` and `agent-events` topics.
- **RAG Pipeline**: Hybrid dense+sparse vector retrieval from Qdrant using Qwen3-Embedding-8B.
- **Chat Endpoint**: `/api/chat` copilot endpoint with PostgreSQL-backed ChatMemoryBuffer.
- **Human-in-the-Loop**: Approval/revision flow at each phase via Gateway-bridged events.
- **Output Management**: Automatic saving of workflow results to timestamped markdown files in `output/`.

### `ai-service/`

- **PDF Ingestion**: `ingest.py` pipeline using DoclingReader for parsing HPE Aruba datasheets and config guides.
- **Hybrid Embedding**: Dense (Qwen/Qwen3-Embedding-8B) and sparse vector generation for Qdrant storage.
- **Token-aware Chunking**: LineBasedTokenChunker with 512-token chunks optimized for table handling.

### `gateway/`

- **API Gateway**: Java/Quarkus service bridging frontend WebSocket ↔ Kafka.
- **WebSocket Server**: Accepts frontend connections at `/chat/{projectId}`.
- **Kafka Producer/Consumer**: Routes `agent-tasks` to AI Service and `agent-events` back to frontend.
- **REST Proxy**: Proxies `/api/chat` and project management endpoints to AI Service.
- **Persistence**: PostgreSQL entities for conversations, messages, agent tasks, and events.

### `Image_generation_service/`

- **Diagram Generation**: D2 → SVG rendering via Kroki.io.
- **Topology Parsing**: Regex-based extraction of building/floor structure from AI output.
- **File Storage**: Local filesystem storage in `generated_diagrams/` with serve/download endpoints.

### `topology_generation/`

- **Validation Gatekeeper**: 4-layer JSON validation (extraction, schema, reference integrity, cross-phase semantics) for React Flow topology data.

### `schemas/`

- **Protocol Definitions**: JSON Schema files defining the WebSocket protocol and Kafka message formats for service-to-service communication.

### `ref_docs/`

- **Documentation**: Comprehensive design documents including system architecture diagram, RAG pipeline diagram, and full project specification PDF.

## Technology Stack

### Backend

- **Python 3.14+** — AI Service, Image Gen, Gatekeeper
- **Java 25 / Quarkus 3.36.1** — Gateway
- **LlamaIndex** — 5-agent workflow orchestration and RAG pipeline
- **Ollama** (Gemma 4 31B, Qwen3 Coder 480B) — LLMs
- **Qdrant** — Hybrid vector database (dense + sparse)
- **Qwen/Qwen3-Embedding-8B** — Embedding model
- **FastAPI** — Web server with async route handling
- **Apache Kafka** — Async message bus between Gateway and AI Service
- **PostgreSQL 15+** — Persistent storage
- **Docling (IBM)** — PDF parsing with structure-aware chunking
- **Firecrawl** — Real-time web search for latest networking data

### Frontend

- **React 19** with Vite 8, Tailwind CSS 4
- **React Router 7** — Multi-step navigation
- **ReactFlow 11** — Interactive topology diagrams via SandpackViewer
- **Axios** — REST API client
- **Marked + KaTeX** — Markdown rendering

---

