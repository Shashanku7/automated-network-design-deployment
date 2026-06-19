import { useNavigate, useParams } from "react-router-dom";
import { useProject } from "../context/ProjectContext";
import { renderMd } from "../utils/renderMd";

export default function BillOfMaterials() {
  const navigate = useNavigate();
  const { projectId } = useParams();
  const { state } = useProject();

  const hasBom = !!state.deviceSelection;

  if (!hasBom) {
    return (
      <div className="p-8 text-center mt-20">
        <span className="material-symbols-outlined text-6xl text-outline mb-4">
          receipt_long
        </span>
        <h2 className="text-xl font-bold text-on-surface mb-2">
          No bill of materials yet
        </h2>
        <p className="text-on-surface-variant mb-6">
          Generate a design first to see recommended equipment.
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

  return (
    <div className="h-full overflow-y-auto p-8 custom-scrollbar">
      <div className="max-w-6xl mx-auto">
        <header className="mb-8 flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
          <div>
            <div className="flex items-center gap-2 text-primary mb-2">
              <span className="material-symbols-outlined text-sm">
                receipt_long
              </span>
              <span className="text-xs font-[family-name:var(--font-mono)] uppercase tracking-[0.2em]">
                Equipment List
              </span>
            </div>
            <h1 className="text-3xl font-bold font-[family-name:var(--font-headline)] text-on-surface tracking-tight">
              Bill of Materials
            </h1>
            <p className="text-on-surface-variant mt-2">
              Phase 3 — Device Selection output.
            </p>
          </div>
        </header>

        <div className="bg-surface-container-low rounded-xl border border-outline-variant/15 overflow-hidden mb-8 shadow-sm">
          <div
            className="md-content bg-surface-container-low rounded-xl border border-outline-variant/15 p-6 text-sm text-on-surface leading-relaxed"
            dangerouslySetInnerHTML={{
              __html: renderMd(state.deviceSelection),
            }}
          />
        </div>

        <div className="flex justify-between items-center">
          <button
            onClick={() => navigate(`/project/${projectId}/design`)}
            className="px-6 py-3 border border-outline-variant/30 text-on-surface font-medium rounded-lg hover:bg-surface-container-high transition-all flex items-center gap-2"
          >
            <span className="material-symbols-outlined">arrow_back</span> Back
            to Design
          </button>
          <div className="flex gap-4">
            <button
              onClick={() => navigate(`/project/${projectId}/topology`)}
              className="px-6 py-3 border border-outline-variant/30 text-on-surface font-medium rounded-lg hover:bg-surface-container-high transition-all flex items-center gap-2"
            >
              Detailed Topology{" "}
              <span className="material-symbols-outlined">account_tree</span>
            </button>
            <button
              onClick={() => navigate(`/project/${projectId}/deployment`)}
              className="px-6 py-3 bg-gradient-to-r from-primary to-primary-container text-on-primary font-bold rounded-lg hover:brightness-110 transition-all flex items-center gap-2 shadow-lg shadow-primary/20"
            >
              Proceed to Deployment{" "}
              <span className="material-symbols-outlined">arrow_forward</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
