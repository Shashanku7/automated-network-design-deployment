import { useNavigate } from 'react-router-dom';
import { useProject } from '../context/ProjectContext';
import SandpackViewer from '../components/SandpackViewer';
import ChatbotSidebar from '../components/ChatbotSidebar';

export default function InteractiveTopology() {
  const navigate = useNavigate();
  const { state } = useProject();

  if (!state.reactCode) {
    return (
      <div className="p-8 text-center mt-20">
        <span className="material-symbols-outlined text-6xl text-outline mb-4">info</span>
        <h2 className="text-xl font-bold text-on-surface mb-2">No interactive topology generated yet</h2>
        <p className="text-on-surface-variant mb-6">Please run the design workflow first.</p>
        <button onClick={() => navigate('/design')} className="px-6 py-3 bg-primary text-on-primary font-bold rounded-lg">
          Go to Design Pipeline
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full overflow-hidden">
      <div className="flex-1 flex flex-col overflow-hidden bg-surface-container">
        <header className="px-6 py-4 bg-surface-container-low border-b border-outline-variant/15 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button onClick={() => navigate('/design')} className="w-10 h-10 rounded-full hover:bg-outline-variant/10 flex items-center justify-center transition-colors text-on-surface-variant">
              <span className="material-symbols-outlined">arrow_back</span>
            </button>
            <div>
              <h1 className="text-lg font-bold text-on-surface">Interactive Network Topology</h1>
              <p className="text-xs text-on-surface-variant">Pan, zoom, and drag nodes</p>
            </div>
          </div>
          <div className="px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-bold border border-primary/20">
            LIVE PREVIEW
          </div>
        </header>

        <div className="flex-1 w-full h-full p-6">
          <div className="w-full h-full rounded-2xl overflow-hidden border border-outline-variant/20 shadow-sm bg-white relative">
            <SandpackViewer reactCode={state.reactCode} onError={(e) => console.error(e)} />
          </div>
        </div>
      </div>

      <ChatbotSidebar />
    </div>
  );
}
