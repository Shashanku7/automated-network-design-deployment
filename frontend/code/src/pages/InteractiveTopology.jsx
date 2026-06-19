import { useNavigate, useParams } from "react-router-dom";
import { useProject } from "../context/ProjectContext";
import SandpackViewer from "../components/SandpackViewer";

export default function InteractiveTopology() {
  const navigate = useNavigate();
  const { projectId } = useParams();
  const { state } = useProject();

  if (!state.reactCode && !state.diagramUrl) {
    return (
      <div className="p-8 text-center mt-20">
        <span className="material-symbols-outlined text-6xl text-outline mb-4">
          info
        </span>
        <h2 className="text-xl font-bold text-on-surface mb-2">
          No topology generated yet
        </h2>
        <p className="text-on-surface-variant mb-6">
          Please run the design workflow first.
        </p>
        <button
          onClick={() => navigate(`/project/${projectId}/design`)}
          className="px-6 py-3 bg-primary text-on-primary font-bold rounded-lg"
        >
          Go to Design Pipeline
        </button>
      </div>
    );
  }

  const isReactCode = !!state.reactCode;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-1 flex flex-col overflow-hidden bg-surface-container">
        <header className="px-6 py-4 bg-surface-container-low border-b border-outline-variant/15 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate(`/project/${projectId}/design`)}
              className="w-10 h-10 rounded-full hover:bg-outline-variant/10 flex items-center justify-center transition-colors text-on-surface-variant"
            >
              <span className="material-symbols-outlined">arrow_back</span>
            </button>
            <div>
              <h1 className="text-lg font-bold text-on-surface">
                Interactive Network Topology
              </h1>
              <p className="text-xs text-on-surface-variant">
                {isReactCode
                  ? "Pan, zoom, and drag nodes"
                  : "Static network topology diagram"}
              </p>
            </div>
          </div>
          <div className="px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-bold border border-primary/20">
            {isReactCode ? "LIVE PREVIEW" : "STATIC DIAGRAM"}
          </div>
        </header>

        <div className="flex-1 w-full h-full p-6">
          {isReactCode ? (
            <div className="w-full h-full rounded-2xl overflow-hidden border border-outline-variant/20 shadow-sm bg-white relative">
              <SandpackViewer
                reactCode={state.reactCode}
                onError={(e) => console.error(e)}
              />
            </div>
          ) : (
            <div className="w-full h-full rounded-2xl overflow-hidden border border-outline-variant/20 shadow-sm bg-surface-container-low flex items-center justify-center p-6">
              <img
                src={state.diagramUrl}
                alt="Network Topology Diagram"
                className="max-w-full max-h-full object-contain"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
