# NetOrch Project Tasks

## Phase 1: Foundation & Frontend (Completed)

- [x] Initialize Git repository
- [x] Scaffold React frontend with Vite
- [x] Configure Tailwind CSS for styling
- [x] Implement core UI components (TopBar, Sidebar)
- [x] Create main page routes (Design, BOM, Topology)
- [x] Implement AI Chat interface for network design
- [x] Draft handover documentation (README, contributions)
- [x] Create contribution mapping (`contrib-map.md`)

## Phase 2: AI & RAG Integration (Completed)

- [x] Set up LLM backend (Python/FastAPI)
- [x] Implement 5-agent RAG pipeline (Qdrant hybrid search, Ollama, Firecrawl)
- [x] Integrate chat API in `frontend/code/src/services/api.js`
- [x] Render diagram of topology in `InteractiveTopology.jsx` (SandpackViewer)
- [x] Fine-tune AI response grounding for enterprise-grade network design

## Phase 3: Backend & Deployment (In Progress)

- [x] Implement Kafka-driven multi-agent workflow (Gateway ↔ AI Service)
- [x] Implement 5-phase pipeline with HITL approval
- [x] Implement Topology Gatekeeper (4-layer validation)
- [x] Implement Diagram Generation Service (D2 → Kroki SVG)
- [ ] Connect regional pricing logic to BOM generation
- [ ] Implement Deployment trigger endpoint (POST `/api/deploy`)
- [ ] Integration testing between Frontend, AI pipeline, and Backend
- [ ] Finalize deployment documentation and hand-over guides
