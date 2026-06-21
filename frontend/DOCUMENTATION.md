# Frontend Documentation

## Project Overview
The frontend of the Automated Network Design and Deployment tool is a modern React application built for high performance, ease of use, and a streamlined network design workflow. It guides users through a sequential pipeline from initial requirements to final deployment configurations.

## Technical Stack & Tools
The application utilizes a cutting-edge frontend stack:

- **Framework:** [React 19](https://react.dev/) - Utilizing the latest features for UI management and performance.
- **Build Tool:** [Vite 8](https://vitejs.dev/) - Providing an extremely fast development environment and optimized production builds.
- **Styling:** [Tailwind CSS 4](https://tailwindcss.com/) - A utility-first CSS framework for rapid UI development and consistent design.
- **Routing:** [React Router 7](https://reactrouter.com/) - Manages the multi-step navigation flow.
- **State Management:** React Context API (`ProjectContext`) - Handles global project data across the design pipeline.
- **API Client:** [Axios](https://axios-http.com/) - For reliable communication with the backend services.
- **Content Rendering:** [Marked](https://marked.js.org/) - To render complex network documentation and summaries from Markdown.
- **Interactive Diagrams:** [ReactFlow 11](https://reactflow.dev/) - For rendering interactive network topology diagrams via the SandpackViewer component.

## Design & Architecture
The UI follows a clean, professional "Enterprise Dashboard" aesthetic.

### Layout Structure
- **AppLayout:** The primary wrapper providing a persistent sidebar and top navigation bar across all views.
- **Sidebar:** Contextual navigation tracking the progress through the design steps.
- **TopBar:** Global actions and project metadata display.

### Design Principles
- **Modern UI:** Minimalist design with a focus on data clarity.
- **Responsiveness:** Fluid layouts that adapt to various screen sizes.
- **Component-Based:** Highly modular code using reusable UI components.

## Application Flow
The application implements a strict pipeline to ensure valid network designs:

1. **Dashboard:** Project overview and recent activity.
2. **Solution Type:** Selection of network architecture (e.g., Campus, Branch, Data Center).
3. **Requirements:** Input of user-specific constraints and scale needs.
4. **Proposed Design:** AI-generated high-level architecture with streaming phases. Events flow: Frontend WS → Gateway → Kafka → AI Service → Kafka → Gateway → Frontend WS.
5. **Bill of Materials (BOM):** AI-generated equipment list from Phase 3 (markdown output).
6. **Detailed Topology:** Tabbed technical view (logical topology, cabling, switch-port mapping).
7. **Interactive Topology:** ReactFlow network diagram rendered via the SandpackViewer component (live code execution sandbox).
8. **Deployment:** Generation of configuration files and deployment status.

## How to Run & Build

### Prerequisites
- Node.js (Latest LTS recommended)
- npm or yarn

### Installation
Navigate to the frontend source directory and install dependencies:
```bash
cd frontend/code
npm install
```

### Development Server
Start the development server with Hot Module Replacement (HMR):
```bash
npm run dev
```
The application will typically be available at `http://localhost:5173`.

### Production Build
Create an optimized production bundle in the `dist` directory:
```bash
npm run build
```

### Preview Production Build
Locally preview the production build:
```bash
npm run preview
```

### Linting
Maintain code quality and style standards:
```bash
npm run lint
```
