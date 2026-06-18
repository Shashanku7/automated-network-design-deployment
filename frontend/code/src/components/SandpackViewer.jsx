import React, { useMemo, useEffect } from 'react';
import ReactFlow, { Background, Controls, MiniMap, Handle, Position, useNodesState, useEdgesState } from 'reactflow';
import 'reactflow/dist/style.css';

function TopologyLoading() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 bg-surface-dim">
      <div className="w-12 h-12 rounded-full border-2 border-primary border-t-transparent animate-spin" />
      <p className="text-on-surface-variant text-sm font-medium">Building interactive topology…</p>
    </div>
  );
}

const ChassisIcon = () => (
  <svg viewBox="-50 -30 100 80" width="80" height="60" style={{ overflow: 'visible' }}>
    <path d="M-40 -20 L20 -20 L40 0 L-20 0 Z" fill="#c8d1d9" stroke="#959da5" strokeWidth="1"/>
    <path d="M-40 -20 L-40 20 L-20 40 L40 40 L40 0 L-20 0 Z" fill="#e1e4e8" stroke="#959da5" strokeWidth="1"/>
    <path d="M-40 -20 L-20 0 L-20 40 L-40 20 Z" fill="#959da5" stroke="#6a737d" strokeWidth="1"/>
    <rect x="-15" y="5" width="2" height="30" fill="#00A3AD" opacity="0.8"/>
    <rect x="-5" y="5" width="2" height="30" fill="#00A3AD" opacity="0.8"/>
    <rect x="5" y="5" width="2" height="30" fill="#00A3AD" opacity="0.8"/>
    <circle cx="30" cy="10" r="2" fill="#3fb950"/>
  </svg>
);

const SwitchIcon = () => (
  <svg viewBox="-45 -15 90 40" width="80" height="38" style={{ overflow: 'visible' }}>
    <path d="M-35 -5 L25 -5 L35 5 L-25 5 Z" fill="#FF8300" stroke="#cc6600" strokeWidth="1"/>
    <path d="M-35 -5 L-35 5 L-25 15 L35 15 L35 5 L25 -5 Z" fill="#f6f8fa" stroke="#d1d5da" strokeWidth="1"/>
    <path d="M-35 -5 L-25 5 L-25 15 L-35 5 Z" fill="#d1d5da" stroke="#959da5" strokeWidth="1"/>
    <rect x="-20" y="7" width="4" height="4" rx="1" fill="#24292e"/>
    <rect x="-8" y="7" width="4" height="4" rx="1" fill="#24292e"/>
    <rect x="4" y="7" width="4" height="4" rx="1" fill="#24292e"/>
    <circle cx="30" cy="10" r="1.5" fill="#3fb950"/>
  </svg>
);

const CameraIcon = () => (
  <svg viewBox="-30 -25 60 50" width="70" height="60" style={{ overflow: 'visible' }}>
    <rect x="-15" y="-15" width="30" height="20" rx="4" fill="#f0f2f5" stroke="#d0d7de" strokeWidth="2" />
    <circle cx="0" cy="-5" r="6" fill="#1a1f36" />
    <path d="M -10 5 L -15 15 L 15 15 L 10 5 Z" fill="#d0d7de" />
  </svg>
);

const WLCIcon = () => (
  <svg viewBox="-30 -25 60 50" width="70" height="60" style={{ overflow: 'visible' }}>
    <rect x="-25" y="-10" width="50" height="20" rx="2" fill="#e1e4e8" stroke="#d0d7de" strokeWidth="2" />
    <circle cx="-15" cy="0" r="2" fill="#00A3AD" />
    <circle cx="-9" cy="0" r="2" fill="#00A3AD" />
    <path d="M 5 -15 A 10 10 0 0 1 25 -15" fill="none" stroke="#00A3AD" strokeWidth="2" />
    <path d="M 10 -10 A 5 5 0 0 1 20 -10" fill="none" stroke="#00A3AD" strokeWidth="2" />
  </svg>
);

const NACIcon = () => (
  <svg viewBox="-30 -25 60 50" width="70" height="60" style={{ overflow: 'visible' }}>
    <rect x="-25" y="-10" width="50" height="20" rx="2" fill="#e1e4e8" stroke="#d0d7de" strokeWidth="2" />
    <path d="M 0 -15 L 10 -10 L 10 2 C 10 8 0 15 0 15 C 0 15 -10 8 -10 2 L -10 -10 Z" fill="#1a1f36" />
    <circle cx="0" cy="-2" r="2" fill="#00A3AD" />
  </svg>
);

const IoTIcon = () => (
  <svg viewBox="-30 -25 60 50" width="70" height="60" style={{ overflow: 'visible' }}>
    <rect x="-12" y="-12" width="24" height="24" rx="4" fill="#f0f2f5" stroke="#00A3AD" strokeWidth="2" />
    <circle cx="0" cy="0" r="4" fill="#1a1f36" />
    <path d="M -12 -6 L -16 -6 M -12 0 L -16 0 M -12 6 L -16 6 M 12 -6 L 16 -6 M 12 0 L 16 0 M 12 6 L 16 6 M -6 -12 L -6 -16 M 0 -12 L 0 -16 M 6 -12 L 6 -16 M -6 12 L -6 16 M 0 12 L 0 16 M 6 12 L 6 16" stroke="#00A3AD" strokeWidth="2" />
  </svg>
);

const StorageIcon = () => (
  <svg viewBox="-30 -25 60 50" width="70" height="60" style={{ overflow: 'visible' }}>
    <path d="M -20 -10 C -20 -15 20 -15 20 -10 L 20 10 C 20 15 -20 15 -20 10 Z" fill="#e1e4e8" stroke="#d0d7de" strokeWidth="2" />
    <path d="M -20 -10 C -20 -5 20 -5 20 -10" fill="none" stroke="#d0d7de" strokeWidth="2" />
    <path d="M -20 0 C -20 5 20 5 20 0" fill="none" stroke="#d0d7de" strokeWidth="2" />
    <circle cx="-10" cy="-5" r="2" fill="#00A3AD" />
    <circle cx="-10" cy="5" r="2" fill="#00A3AD" />
  </svg>
);

const LoadBalancerIcon = () => (
  <svg viewBox="-30 -25 60 50" width="70" height="60" style={{ overflow: 'visible' }}>
    <rect x="-25" y="-10" width="50" height="20" rx="2" fill="#e1e4e8" stroke="#d0d7de" strokeWidth="2" />
    <path d="M -15 -15 L 0 0 L 15 -15 M 0 0 L 0 15 M -5 -10 L 5 -10" stroke="#FF8300" strokeWidth="2" fill="none" />
    <circle cx="0" cy="0" r="3" fill="#1a1f36" />
  </svg>
);

const APIcon = () => (
  <svg viewBox="-20 -20 40 40" width="50" height="50" style={{ overflow: 'visible' }}>
    <rect x="-15" y="-15" width="30" height="30" rx="8" fill="#ffffff" stroke="#e1e4e8" strokeWidth="2"/>
    <circle cx="0" cy="0" r="4" fill="#00A3AD" opacity="0.3"/>
    <path d="M-6 -3 Q0 -11 6 -3" fill="none" stroke="#00A3AD" strokeWidth="1.5"/>
    <path d="M-10 -7 Q0 -18 10 -7" fill="none" stroke="#00A3AD" strokeWidth="1.5" opacity="0.5"/>
    <circle cx="12" cy="-12" r="2" fill="#3fb950"/>
  </svg>
);

const ServerIcon = () => (
  <svg viewBox="-20 -35 50 60" width="60" height="60" style={{ overflow: 'visible' }}>
    <path d="M-15 -30 L15 -30 L25 -20 L-5 -20 Z" fill="#00A3AD" stroke="#007e85" strokeWidth="1"/>
    <path d="M-15 -30 L-15 10 L-5 20 L25 20 L25 -20 L15 -30 Z" fill="#f6f8fa" stroke="#d1d5da" strokeWidth="1"/>
    <path d="M-15 -30 L-5 -20 L-5 20 L-15 10 Z" fill="#d1d5da" stroke="#959da5" strokeWidth="1"/>
    <rect x="0" y="-10" width="20" height="2" fill="#d1d5da"/>
    <rect x="0" y="-4" width="20" height="2" fill="#d1d5da"/>
    <circle cx="22" cy="-15" r="2" fill="#3fb950"/>
  </svg>
);

const GatewayIcon = () => (
  <svg viewBox="-30 -20 60 45" width="70" height="50" style={{ overflow: 'visible' }}>
    <path d="M-25 -15 L15 -15 L25 -5 L-15 -5 Z" fill="#f85149" stroke="#da3633" strokeWidth="1"/>
    <path d="M-25 -15 L-25 10 L-15 20 L25 20 L25 -5 L15 -15 Z" fill="#ffffff" stroke="#d1d5da" strokeWidth="1"/>
    <path d="M-25 -15 L-15 -5 L-15 20 L-25 10 Z" fill="#d1d5da" stroke="#959da5" strokeWidth="1"/>
    <path d="M0 5 L10 5" stroke="#f85149" strokeWidth="2" opacity="0.6"/>
    <path d="M5 0 L5 10" stroke="#f85149" strokeWidth="2" opacity="0.6"/>
  </svg>
);

const CloudIcon = () => (
  <svg viewBox="-50 -50 120 80" width="100" height="70" style={{ overflow: 'visible' }}>
    <defs>
      <linearGradient id="cloudGradSV" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" style={{ stopColor: '#f0f8ff', stopOpacity: 1 }}/>
        <stop offset="100%" style={{ stopColor: '#add8e6', stopOpacity: 1 }}/>
      </linearGradient>
    </defs>
    <path
      d="M-40 0 Q-40 -20 -20 -20 Q-20 -40 10 -40 Q40 -40 40 -20 Q55 -20 55 0 Q55 15 35 15 L-20 15 Q-40 15 -40 0 Z"
      fill="url(#cloudGradSV)" stroke="#99bbcc" strokeWidth="1.5"
    />
  </svg>
);

const LaptopIcon = () => (
  <svg viewBox="-25 -20 50 40" width="60" height="50" style={{ overflow: 'visible' }}>
    <rect x="-20" y="-15" width="40" height="25" rx="2" fill="#d1d5da" stroke="#959da5" strokeWidth="1"/>
    <rect x="-18" y="-13" width="36" height="21" rx="1" fill="#24292e"/>
    <path d="M-24 10 L24 10 L28 15 L-28 15 Z" fill="#e1e4e8" stroke="#959da5" strokeWidth="1"/>
    <rect x="-5" y="11" width="10" height="3" rx="0.5" fill="#d1d5da"/>
    <circle cx="20" cy="-15" r="2" fill="#3fb950"/>
  </svg>
);

const PhoneIcon = () => (
  <svg viewBox="-20 -20 40 40" width="50" height="50" style={{ overflow: 'visible' }}>
    <rect x="-15" y="-10" width="30" height="25" rx="3" fill="#2d333b" stroke="#1c2128" strokeWidth="1"/>
    <rect x="-12" y="-7" width="24" height="8" rx="1" fill="#c8e1ff"/>
    <rect x="-12" y="4" width="4" height="2" fill="#6e7681"/>
    <rect x="-5" y="4" width="4" height="2" fill="#6e7681"/>
    <rect x="2" y="4" width="4" height="2" fill="#6e7681"/>
    <rect x="-12" y="8" width="4" height="2" fill="#6e7681"/>
    <rect x="-5" y="8" width="4" height="2" fill="#6e7681"/>
    <rect x="2" y="8" width="4" height="2" fill="#6e7681"/>
    <path d="M10 -15 L-15 -15 A 3 3 0 0 0 -18 -12 L-18 10 A 3 3 0 0 0 -15 13 L-12 13 L-12 -12 L10 -12 Z" fill="#24292e"/>
    <circle cx="15" cy="-15" r="2" fill="#3fb950"/>
  </svg>
);

const PrinterIcon = () => (
  <svg viewBox="-25 -25 50 50" width="60" height="60" style={{ overflow: 'visible' }}>
    <rect x="-12" y="-20" width="24" height="15" fill="#ffffff" stroke="#d1d5da" strokeWidth="1"/>
    <line x1="-8" y1="-15" x2="8" y2="-15" stroke="#e1e4e8" strokeWidth="1"/>
    <line x1="-8" y1="-12" x2="8" y2="-12" stroke="#e1e4e8" strokeWidth="1"/>
    <rect x="-20" y="-5" width="40" height="20" rx="4" fill="#e1e4e8" stroke="#959da5" strokeWidth="1"/>
    <rect x="-15" y="8" width="30" height="12" fill="#24292e"/>
    <rect x="-12" y="10" width="24" height="12" fill="#ffffff" stroke="#d1d5da" strokeWidth="1"/>
    <circle cx="14" cy="0" r="2" fill="#3fb950"/>
    <circle cx="14" cy="4" r="1.5" fill="#f85149"/>
  </svg>
);

const IPTVIcon = () => (
  <svg viewBox="-30 -25 60 50" width="70" height="60" style={{ overflow: 'visible' }}>
    <rect x="-25" y="-15" width="50" height="30" rx="2" fill="#1a1a1a" stroke="#000000" strokeWidth="1"/>
    <rect x="-23" y="-13" width="46" height="26" fill="#0366d6"/>
    <path d="M-10 15 L10 15 L15 20 L-15 20 Z" fill="#6e7681"/>
    <line x1="0" y1="15" x2="0" y2="20" stroke="#1a1a1a" strokeWidth="4"/>
    <circle cx="20" cy="12" r="1.5" fill="#3fb950"/>
  </svg>
);

const ICON_MAP = {
  Chassis: ChassisIcon,
  Switch: SwitchIcon,
  AP: APIcon,
  Server: ServerIcon,
  Gateway: GatewayIcon,
  Cloud: CloudIcon,
  Laptop: LaptopIcon,
  Phone: PhoneIcon,
  Printer: PrinterIcon,
  IPTV: IPTVIcon,
  Camera: CameraIcon,
  WLC: WLCIcon,
  NAC: NACIcon,
  IoT: IoTIcon,
  Storage: StorageIcon,
  LoadBalancer: LoadBalancerIcon,
};

function CustomNode({ data }) {
  const lines = (data.label || '').split('\n');
  const IconComponent = ICON_MAP[data.iconType] || SwitchIcon;

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      fontFamily: "'Segoe UI', 'Arial', sans-serif",
      padding: '8px 6px 6px 6px',
      minWidth: '100px',
      cursor: 'move',
    }}>
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: '#00A3AD', width: 7, height: 7, border: '1px solid #007e85' }}
      />
      <IconComponent />
      <div style={{ textAlign: 'center', marginTop: '6px', lineHeight: 1.4 }}>
        {lines[0] && (
          <div style={{ fontWeight: 'bold', fontSize: '12px', color: '#1a1a1a' }}>
            {lines[0]}
          </div>
        )}
        {lines[1] && (
          <div style={{ fontFamily: 'Consolas, monospace', fontSize: '11px', fontWeight: 'bold', color: '#00A3AD' }}>
            {lines[1]}
          </div>
        )}
        {lines[2] && (
          <div style={{ fontStyle: 'italic', fontSize: '10px', color: '#666' }}>
            {lines[2]}
          </div>
        )}
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: '#00A3AD', width: 7, height: 7, border: '1px solid #007e85' }}
      />
    </div>
  );
}

const nodeTypes = { custom: CustomNode };

function extractJSONArrays(reactCode) {
  try {
    const nodesMatch = reactCode.match(/const\s+nodes\s*=\s*(\[[\s\S]*?\])\s*;/);
    const edgesMatch = reactCode.match(/const\s+edges\s*=\s*(\[[\s\S]*?\])\s*;/);
    if (!nodesMatch || !edgesMatch) {
      throw new Error('Could not find nodes or edges in generated React code.');
    }
    const nodes = JSON.parse(nodesMatch[1]);
    const edges = JSON.parse(edgesMatch[1]);
    return { nodes, edges };
  } catch (err) {
    console.error('[SandpackViewer] Failed to parse nodes and edges:', err);
    return null;
  }
}

export default function SandpackViewer({ reactCode, onError }) {
  const data = useMemo(() => reactCode ? extractJSONArrays(reactCode) : null, [reactCode]);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    if (data) {
      setNodes(data.nodes);
      setEdges(data.edges);
    }
  }, [data, setNodes, setEdges]);

  if (!reactCode) {
    return <TopologyLoading />;
  }

  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 bg-surface-dim text-error p-4 text-center">
        <span className="material-symbols-outlined text-4xl">warning</span>
        <p className="text-sm font-medium">Failed to parse topology code.</p>
        <p className="text-xs text-outline">Please check console logs or request a change.</p>
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height: '100%', background: '#fdfdfd', position: 'relative' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        nodesConnectable={false}
        nodesDraggable={true}
        elementsSelectable={true}
        defaultEdgeOptions={{ type: 'smoothstep' }}
      >
        <Background color="#e8e8e8" gap={20} />
        <Controls />
        <MiniMap nodeStrokeColor="#00A3AD" nodeColor="#e1e4e8" />
      </ReactFlow>
    </div>
  );
}
