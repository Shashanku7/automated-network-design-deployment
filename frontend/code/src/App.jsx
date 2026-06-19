/**
 * App.jsx — Router configuration
 *
 * Defines the complete user flow:
 * Dashboard → Solution Type → Requirements → Design → BOM → Topology → Deployment
 *
 * All pages are wrapped in AppLayout (persistent sidebar + topbar).
 */
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ProjectProvider } from "./context/ProjectContext";
import AppLayout from "./layouts/AppLayout";
import Dashboard from "./pages/Dashboard";
import SolutionType from "./pages/SolutionType";
import Requirements from "./pages/Requirements";
import ProposedDesign from "./pages/ProposedDesign";
import BillOfMaterials from "./pages/BillOfMaterials";
import DetailedTopology from "./pages/DetailedTopology";
import InteractiveTopology from "./pages/InteractiveTopology";
import Deployment from "./pages/Deployment";

export default function App() {
  return (
    <ProjectProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="project/new" element={<SolutionType />} />
            <Route path="project/:projectId" element={<Dashboard />} />
            <Route
              path="project/:projectId/requirements"
              element={<Requirements />}
            />
            <Route
              path="project/:projectId/design"
              element={<ProposedDesign />}
            />
            <Route
              path="project/:projectId/bom"
              element={<BillOfMaterials />}
            />
            <Route
              path="project/:projectId/topology"
              element={<DetailedTopology />}
            />
            <Route
              path="project/:projectId/interactive-topology"
              element={<InteractiveTopology />}
            />
            <Route
              path="project/:projectId/deployment"
              element={<Deployment />}
            />
          </Route>
        </Routes>
      </BrowserRouter>
    </ProjectProvider>
  );
}
