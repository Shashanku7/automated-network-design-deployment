import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ProjectProvider } from "./context/ProjectContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import AppLayout from "./layouts/AppLayout";
import Dashboard from "./pages/Dashboard";
import SolutionType from "./pages/SolutionType";
import Requirements from "./pages/Requirements";
import ProposedDesign from "./pages/ProposedDesign";
import BillOfMaterials from "./pages/BillOfMaterials";
import DetailedTopology from "./pages/DetailedTopology";
import InteractiveTopology from "./pages/InteractiveTopology";
import Deployment from "./pages/Deployment";

function CallbackHandler() {
  const { isAuthenticated } = useAuth();
  if (isAuthenticated) return <Navigate to="/" replace />;
  return (
    <div className="flex items-center justify-center h-screen bg-surface">
      <div className="text-on-surface-variant text-sm">Completing sign in...</div>
    </div>
  );
}

function ProtectedRoutes() {
  const { isAuthenticated, ready, login } = useAuth();
  if (!ready) return null;
  if (!isAuthenticated) {
    login();
    return null;
  }
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="project/new" element={<SolutionType />} />
        <Route path="project/:projectId" element={<Dashboard />} />
        <Route path="project/:projectId/requirements" element={<Requirements />} />
        <Route path="project/:projectId/design" element={<ProposedDesign />} />
        <Route path="project/:projectId/bom" element={<BillOfMaterials />} />
        <Route path="project/:projectId/topology" element={<DetailedTopology />} />
        <Route path="project/:projectId/interactive-topology" element={<InteractiveTopology />} />
        <Route path="project/:projectId/deployment" element={<Deployment />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <ProjectProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/callback" element={<CallbackHandler />} />
            <Route path="/*" element={<ProtectedRoutes />} />
          </Routes>
        </BrowserRouter>
      </ProjectProvider>
    </AuthProvider>
  );
}
