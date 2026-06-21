# Contribution Mapping

This document maps project contributors to their specific technical contributions based on repository history and project documentation.

| Contributor | Roles & Key Contributions |
| :---------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Shashank U** | **Frontend Lead & Architecture**<br>• Initialized the project and React/Vite scaffolding.<br>• Developed core UI components (Sidebar, TopBar, AppLayout) and ProjectContext state management.<br>• Implemented all 8 feature pages (Dashboard → Deployment) with React Router 7.<br>• Built WebSocket + REST API integration layer (`api.js`). |
| **Shashank Shantharam Nayak** | **API Gateway & Backend Services**<br>• Implemented the Java/Quarkus Gateway (WebSocket ↔ Kafka bridge, REST proxy, PostgreSQL persistence).<br>• Created the Kafka producer/consumer for agent task distribution.<br>• Implemented the 4-layer Topology Gatekeeper validation service.<br>• Contributed to schema definitions and protocol design. |
| **Priyam Sarkar** | **AI Workflow Pipeline & RAG**<br>• Implemented document chunking (Docling) and embedding (Qwen3-Embedding-8B) for Qdrant vector store.<br>• Designed the 5-agent LLM pipeline (Prompt Rephraser, Topology Designer, Device Selector, React Architect, CLI Generator).<br>• Integrated hybrid dense+sparse search, Firecrawl web search, and Ollama LLM selection. |
| **Fazal Ali Sheikh** | **Image Generation Service**<br>• Built the D2 → SVG diagram generation microservice using Kroki.io.<br>• Implemented topology text parsing and D2 code generation from AI output.<br>• Set up local file storage and serve/download endpoints for generated diagrams. |
| **Tummala Gowtham Jignas** | **AI Service Backend & Real-time Communication**<br>• Built the FastAPI server with Kafka-driven multi-agent orchestrator (`app.py`, `routes.py`, `kafka_handler.py`).<br>• Implemented agent streaming events (TOKEN, TOOL_CALL, TOOL_RESULT, FINAL_ANSWER) over Kafka.<br>• Managed REST API endpoints (`/api/chat`, `/api/chat-history`) and PostgreSQL ChatMemoryBuffer persistence.<br>• Implemented Phase 4 gatekeeper integration with auto-correction loop. |

