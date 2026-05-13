/**
 * DetailedTopology — Technical topology with tabs
 * 
 * Tabs: Logical Topology | Cabling Map | Switch-Port Mapping
 * Has a "Simple View" / "Technical View" toggle.
 * Each tab has a placeholder for AI-generated content.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../context/ProjectContext';

const tabs = [
  { id: 'logical', label: 'Logical Topology', icon: 'account_tree' },
  { id: 'cabling', label: 'Cabling Map', icon: 'cable' },
  { id: 'ports', label: 'Switch-Port Mapping', icon: 'settings_ethernet' },
];

export default function DetailedTopology() {
  const navigate = useNavigate();
  const { state } = useProject();
  const [activeTab, setActiveTab] = useState('logical');
  const [simpleView, setSimpleView] = useState(true);

  if (!state.proposedDesign) {
    return (
      <div className="p-8 text-center mt-20">
        <span className="material-symbols-outlined text-6xl text-outline mb-4">account_tree</span>
        <h2 className="text-xl font-bold text-on-surface mb-2">No topology available</h2>
        <p className="text-on-surface-variant mb-6">Generate a design first.</p>
        <button onClick={() => navigate('/requirements')} className="px-6 py-3 bg-primary text-on-primary font-bold rounded-lg">Go to Requirements</button>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-8 custom-scrollbar">
      <div className="max-w-6xl mx-auto">
      <header className="mb-8 flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold font-[family-name:var(--font-headline)] text-on-surface tracking-tight">Detailed Topology</h1>
          <p className="text-on-surface-variant mt-2">In-depth view of your network architecture.</p>
        </div>
        {/* Simple/Technical toggle */}
        <div className="flex items-center gap-3 bg-surface-container-low px-4 py-2 rounded-lg border border-outline-variant/15">
          <span className={`text-sm font-medium ${simpleView ? 'text-primary' : 'text-on-surface-variant'}`}>Simple</span>
          <button onClick={() => setSimpleView(!simpleView)}
            className={`w-12 h-6 rounded-full transition-all relative ${!simpleView ? 'bg-primary' : 'bg-surface-container-highest'}`}>
            <div className={`w-5 h-5 rounded-full bg-white absolute top-0.5 transition-transform ${!simpleView ? 'translate-x-6' : 'translate-x-0.5'}`} />
          </button>
          <span className={`text-sm font-medium ${!simpleView ? 'text-primary' : 'text-on-surface-variant'}`}>Technical</span>
        </div>
      </header>

      {/* Tab Navigation */}
      <div className="flex gap-2 mb-8 border-b border-outline-variant/10 pb-1">
        {tabs.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-5 py-3 text-sm font-medium rounded-t-lg transition-all ${
              activeTab === tab.id
                ? 'bg-surface-container-low text-primary border-b-2 border-primary'
                : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low/50'
            }`}>
            <span className="material-symbols-outlined text-lg">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="bg-surface-container-low rounded-xl border border-outline-variant/15 p-8 min-h-[400px] flex items-center justify-center">
        {activeTab === 'logical' && (
          state.diagramUrl ? (
            <div className="w-full">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary text-lg">schema</span>
                  <h3 className="text-lg font-bold text-on-surface">
                    {simpleView ? 'Network Map' : 'Logical Topology'}
                  </h3>
                </div>
                <a href={state.diagramDownloadUrl || state.diagramUrl} download="network_topology.svg"
                  className="flex items-center gap-1.5 px-4 py-2 bg-primary/15 text-primary text-sm font-bold rounded-lg hover:bg-primary/25 transition-colors">
                  <span className="material-symbols-outlined text-lg">download</span>
                  Download Diagram
                </a>
              </div>
              <div className="bg-white rounded-xl p-4 flex items-center justify-center overflow-auto max-h-[600px]">
                <img src={state.diagramUrl} alt="Network Topology Diagram" className="max-w-full object-contain" />
              </div>
            </div>
          ) : (
            <div className="text-center">
              <span className="material-symbols-outlined text-6xl text-outline/30 mb-4">account_tree</span>
              <h3 className="text-lg font-bold text-on-surface mb-2">Logical Topology</h3>
              <p className="text-on-surface-variant text-sm max-w-md">
                {simpleView
                  ? 'A visual map showing how your buildings and devices are connected.'
                  : 'Layer 2/3 topology with VLAN segmentation, OSPF areas, and inter-switch trunk links.'}
              </p>
              <p className="text-xs text-outline mt-4 italic">
                Generate a design to see the network topology diagram here.
              </p>
            </div>
          )
        )}
        {activeTab === 'cabling' && (
          <div className="text-center">
            <span className="material-symbols-outlined text-6xl text-outline/30 mb-4">cable</span>
            <h3 className="text-lg font-bold text-on-surface mb-2">Cabling Map</h3>
            <p className="text-on-surface-variant text-sm max-w-md">
              {simpleView
                ? 'Shows which cables connect each building and floor.'
                : 'Structured cabling layout with fiber/copper runs, patch panel assignments, and riser diagrams.'}
            </p>
            <p className="text-xs text-outline mt-4 italic">
              // TODO: AI team — render cabling diagram here
            </p>
          </div>
        )}
        {activeTab === 'ports' && (
          <div className="text-center">
            <span className="material-symbols-outlined text-6xl text-outline/30 mb-4">settings_ethernet</span>
            <h3 className="text-lg font-bold text-on-surface mb-2">Switch-Port Mapping</h3>
            <p className="text-on-surface-variant text-sm max-w-md">
              {simpleView
                ? 'Shows which devices plug into which ports on each switch.'
                : 'Port-level assignments with VLAN tags, PoE allocation, and interface descriptions.'}
            </p>
            <p className="text-xs text-outline mt-4 italic">
              // TODO: [AI TEAM] — render port mapping table here based on generated topology data
            </p>
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="flex justify-between mt-8">
        <button onClick={() => navigate('/bom')} className="px-6 py-3 border border-outline-variant/30 text-on-surface font-medium rounded-lg hover:bg-surface-container-high transition-all flex items-center gap-2">
          <span className="material-symbols-outlined">arrow_back</span> Bill of Materials
        </button>
        <button onClick={() => navigate('/deployment')} className="px-6 py-3 bg-gradient-to-r from-primary to-primary-container text-on-primary font-bold rounded-lg hover:brightness-110 transition-all flex items-center gap-2">
          Proceed to Deployment <span className="material-symbols-outlined">arrow_forward</span>
        </button>
      </div>
    </div>
    </div>
  );
}
