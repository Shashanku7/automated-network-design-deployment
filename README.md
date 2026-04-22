# NetOrch - Network Orchestration System

Developed as part of the **HPE CPP** initiative, NetOrch is an AI-powered dashboard that allows non-technical business users to design and deploy enterprise-grade networks without needing technical expertise.

## Core Features
*   **Grounded Design Copilot**: A RAG-powered AI assistant for natural language network design.
*   **Logic-Based BOM**: Automated Bill of Materials generation with regional pricing.
*   **Visual Topology**: Plain-English network diagrams and deployment guides.
*   **Handover Ready**: Fully documented code with clear integration points for AI and Backend teams.

## Handover Guide
*   **AI Team**: Integrate LLM and RAG pipelines in `src/services/api.js`.
*   **Backend Team**: Connect pricing and deployment triggers in `src/services/api.js`.
*   **Project Lead**: Reference the detailed TODO comments tagged `[AI TEAM]` and `[BACKEND TEAM]` throughout the codebase.

## Quick Start
```bash
npm install
npm run dev
```
