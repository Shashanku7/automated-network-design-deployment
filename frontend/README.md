# Frontend — Network Design SPA

React 19 single-page application for the NetOrch network design pipeline. Guides users through 7 steps from requirements to deployment.

**Port:** 5173

## Tech Stack

| Tool | Version |
|------|---------|
| React | 19 |
| Vite | 8 |
| Tailwind CSS | 4 |
| React Router | 7 |
| ReactFlow | 11 |
| Axios | — |
| Marked + KaTeX | — |

## Pipeline

1. **Dashboard** — Project overview and metrics
2. **Solution Type** — Network architecture selection (Campus, Branch, DC)
3. **Requirements** — Natural language constraint input
4. **Proposed Design** — AI-generated high-level architecture
5. **Bill of Materials** — AI-generated equipment list (Phase 3 markdown output)
6. **Detailed Topology** — Tabbed technical view (logical, cabling, ports)
7. **Interactive Topology** — ReactFlow diagram rendered via Sandpack
8. **Deployment** — Config generation and deploy status

## Setup

```bash
cd frontend/code
npm install
```

## Running

```bash
npm run dev          # dev server with HMR → http://localhost:5173
npm run build        # production build → dist/
npm run preview      # preview production build
npm run lint         # ESLint
```

## Vite Proxy Config

The dev server proxies backend requests:

| Prefix | Target |
|--------|--------|
| `/ws` | `ws://localhost:8000` (AI Service) |
| `/api` | `http://localhost:8080` (Gateway) |
| `/api/diagrams` | `http://localhost:8001` (Image Gen) |

## WebSocket Protocol

The frontend connects via `api.js` to the Gateway's WebSocket (`ws://localhost:8080/ws`). Messages follow the schema in [`schemas/ws-protocol.json`](../schemas/ws-protocol.json).

Key event types: `USER_INPUT`, `AGENT_EVENT`, `TOOL_CALL`, `TOOL_RESULT`, `APPROVAL_REQ`, `WORKFLOW_COMPLETE`.

## Project Structure

```
code/
  src/
    App.jsx              — Router setup
    pages/               — 8 page components
    components/          — Sidebar, TopBar, shared UI
    services/api.js      — WebSocket + REST API layer
    contexts/            — ProjectContext (global state)
```

## Key Files

| File | Purpose |
|------|---------|
| `src/App.jsx` | Route definitions |
| `src/pages/DetailedTopology.jsx` | Tabbed technical topology view |
| `src/pages/InteractiveTopology.jsx` | Interactive ReactFlow diagram (Sandpack) |
| `src/services/api.js` | WebSocket handler and API client |
| `vite.config.js` | Dev proxy, build config |

For detailed UI/UX docs, see [`DOCUMENTATION.md`](./DOCUMENTATION.md).
