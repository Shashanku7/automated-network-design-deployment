# NetOrch - Network Orchestration System

## Project Context

This project is developed as part of the **HPE CPP** initiative to advance AI-driven network orchestration and deployment automation.

## Project Overview

NetOrch is a production-ready network orchestration dashboard designed to simplify enterprise network design and deployment. It leverages AI-driven design (Grounded Design Copilot) and a logic-based Bill of Materials system to provide a seamless experience for network engineers.

The application is built as a high-fidelity prototype with a clear architectural path for backend and AI service integration.

## Technical Stack

*   Core: React 18 with Vite
*   Styling: Vanilla CSS with modern flexbox and grid layouts
*   Routing: React Router v6
*   State Management: React Context API (ProjectContext)
*   Icons: Google Material Symbols (Rounded)
*   Design System: Material Design 3 (M3) principles with custom HPE branding

## Project Structure

*   /src/components: Reusable UI components (Sidebar, TopBar, Chat, etc.)
*   /src/pages: Page-level components representing major application views
*   /src/services: API service layer with stubs for AI and Backend integration
*   /src/context: Global state management for project requirements and design state
*   /src/layouts: Shared application layout wrappers

## Development Roadmap and Handover

This project has been explicitly documented with TODO comments to guide specific engineering teams.

### AI Engineering Team

The AI team is responsible for replacing the static design generation with a live RAG (Retrieval-Augmented Generation) pipeline.
*   Relevant Files: src/services/api.js, src/pages/ProposedDesign.jsx, src/pages/DetailedTopology.jsx
*   Key Tasks: Connect to LLM services, implement topology diagram generation, and integrate the Aruba documentation vector database.

### Backend Engineering Team

The backend team is responsible for data persistence, orchestration triggers, and external service integration.
*   Relevant Files: src/services/api.js, src/components/TopBar.jsx, src/pages/BillOfMaterials.jsx, src/pages/Deployment.jsx
*   Key Tasks: Replace mock project lists with real database queries, implement the search API, connect to the Global Pricing Service, and trigger Kafka-based deployment pipelines.

### Frontend Engineering Team

The frontend is structurally complete but can be further polished with real-time web socket updates.
*   Key Tasks: Replace the mock progress indicators in the Deployment page with real-time status updates via WebSockets or long polling.

## Getting Started

1. Install dependencies: npm install
2. Run development server: npm run dev
3. Build for production: npm run build
