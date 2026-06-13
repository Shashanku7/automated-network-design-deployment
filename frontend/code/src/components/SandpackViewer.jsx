/**
 * SandpackViewer.jsx
 *
 * Renders Agent 4's React Flow code live inside an embedded Sandpack iframe.
 * Wrapped in a React Error Boundary so any compile/runtime crash shows
 * a friendly "Refining diagram..." spinner instead of a red crash screen.
 *
 * Props:
 *   reactCode {string} — The full React JSX string from Agent 4 (via backend).
 */

import { Component } from 'react';
import { Sandpack } from '@codesandbox/sandpack-react';

// ─── Error Boundary ───────────────────────────────────────────────────────────
class TopologyErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('[TopologyErrorBoundary] Sandpack crash caught:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full gap-4 bg-surface-dim">
          <div className="flex gap-1">
            <span className="w-3 h-3 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0s' }} />
            <span className="w-3 h-3 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0.15s' }} />
            <span className="w-3 h-3 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0.3s' }} />
          </div>
          <p className="text-on-surface-variant text-sm font-medium">Refining diagram layout…</p>
          <p className="text-outline text-xs">The AI is correcting the topology code automatically.</p>
        </div>
      );
    }
    return this.props.children;
  }
}

// ─── Loading Placeholder ──────────────────────────────────────────────────────
function TopologyLoading() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 bg-surface-dim">
      <div className="w-12 h-12 rounded-full border-2 border-primary border-t-transparent animate-spin" />
      <p className="text-on-surface-variant text-sm font-medium">Building interactive topology…</p>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
export default function SandpackViewer({ reactCode }) {
  if (!reactCode) {
    return <TopologyLoading />;
  }

  return (
    <TopologyErrorBoundary>
      <Sandpack
        template="react"
        files={{
          '/App.js': {
            code: reactCode,
            active: true,
          },
        }}
        customSetup={{
          dependencies: {
            reactflow: '11.11.4',
            dagre: '0.8.5',
          },
        }}
        options={{
          showEditor: false,          // Hide code panel — show only the live preview
          showConsole: false,
          showNavigator: false,
          showTabs: false,
          editorHeight: 0,
          externalResources: [],
          recompileMode: 'immediate',
          recompileDelay: 300,
        }}
        theme="dark"
        style={{ height: '100%', width: '100%' }}
      />
    </TopologyErrorBoundary>
  );
}
