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

- **Architecture**: Scaffolding of the React application using Vite.
- **UI Components**: Implementation of core layout components including `Sidebar`, `TopBar`, and `AppLayout`. **State Management**: Implementation of `ProjectContext` for global application state.
- **Feature Pages**:
  - **Dashboard**: Project overview and metrics.
  - **Requirements**: Natural language input interface for network design.
  - **Solution Type**: Logic for selecting between different networking solutions.
  - **Proposed Design**: Visual representation and descriptions of AI-generated designs.
  - **Bill of Materials (BOM)**: Automated pricing and equipment lists.
  - **Detailed Topology**: Technical port mapping and configuration guides.
  - **Deployment**: Progress tracking for network deployment.
- **Services**: `api.js` integration layer for AI and Backend services.

### `ref_docs/`

- **Documentation**: Comprehensive design documents including:
  - `Backend_Design.jpg`: System architecture and data flow.
  - `RAG_Workflow.jpg`: AI Retrieval-Augmented Generation pipeline.
  - `CPP_Project_Automated_Network_Design_and_Deployment_Latest.pdf`: Full project documentation and specifications.

### Root Level (`/home/coe/Documents/project`)

### `main.py`

- **3-Phase AI Workflow**: Implementation of the multi-agent workflow system using LlamaIndex AgentWorkflow.
  - **Phase 1 – Prompt Rephraser**: Network Development Prompt Engineer agent that refines user requests into structured prompts.
  - **Phase 2 – Topology Designer**: Senior Network Topology Architect agent that designs network topologies including VSF, VSX, LAG, and QoS.
  - **Phase 3 – Device Selector**: Network Hardware Specialist agent that selects devices from RAG knowledge base.
- **Human-in-the-Loop (HITL)**: Interactive approval system allowing users to approve or request revisions at each phase.
- **RAG Integration**: Hybrid dense+sparse retrieval from Qdrant vector database using Qwen embedding model.
- **CLI Interface**: Command-line entry point with argparse for running workflows.

### `ingest.py`

- **PDF Processing**: Document ingestion pipeline using DoclingReader for parsing HPE Aruba networking equipment datasheets.
- **Hybrid Embedding**: Dense (Qwen/Qwen3-Embedding-8B) and sparse vector generation for Qdrant storage.
- **Token-aware Chunking**: LineBasedTokenChunker with 512-token chunks optimized for table handling.
- **Qdrant Uploader**: Batch upsert of hybrid-embedded chunks to Qdrant collection.

### `search.py`

- **Query Interface**: Standalone script for querying the Qdrant knowledge base.
- **Hybrid Search**: Dense + sparse vector retrieval for networking component specifications.

### `webapp/app.py`

- **FastAPI Server**: Web application serving the frontend and exposing API endpoints.
- **WebSocket Streaming**: Real-time event streaming for the 3-phase AI workflow (phase_start, agent_input, tool_call, rag_result, agent_response, approval_request, workflow_complete).
- **Chat Endpoint**: `/api/chat` endpoint for the AI copilot sidebar.
- **Output Management**: Automatic saving of workflow results to timestamped markdown files in `output/`.

## Technology Stack

### Backend
- **Python 3.14+**
- **LlamaIndex**: Agent workflow and RAG pipeline
- **Ollama** (Gemma 4 31B): LLM for AI phases
- **Qdrant**: Hybrid vector database (dense + sparse)
- **Qwen/Qwen3-Embedding-8B**: Embedding model
- **FastAPI**: Web server with WebSocket support
- **Docling**: PDF parsing
---
