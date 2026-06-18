import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../context/ProjectContext';
import { runWorkflow, sendApproval, sendRevision } from '../services/api';
import { marked } from 'marked';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import ChatbotSidebar from '../components/ChatbotSidebar';

marked.setOptions({ gfm: true, breaks: true });

function renderMd(text) {
  if (!text) return '';

  const mathPlaceholders = [];

  let processed = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, expr) => {
    try {
      const html = katex.renderToString(expr.trim(), { displayMode: true, throwOnError: false });
      mathPlaceholders.push(html);
    } catch {
      mathPlaceholders.push(`<span class="katex-error">$$${expr}$$</span>`);
    }
    return `%%MATH_BLOCK_${mathPlaceholders.length - 1}%%`;
  });

  processed = processed.replace(/\$([^\$\n]+?)\$/g, (_, expr) => {
    try {
      const html = katex.renderToString(expr.trim(), { displayMode: false, throwOnError: false });
      mathPlaceholders.push(html);
    } catch {
      mathPlaceholders.push(`<span class="katex-error">$${expr}$</span>`);
    }
    return `%%MATH_BLOCK_${mathPlaceholders.length - 1}%%`;
  });

  let html = marked.parse(processed);
  html = html.replace(/%%MATH_BLOCK_(\d+)%%/g, (_, idx) => mathPlaceholders[parseInt(idx)]);
  return html;
}

export default function ProposedDesign() {
  const navigate = useNavigate();
  const { state, dispatch } = useProject();
  const [wsRef, setWsRef] = useState(null);
  const [status, setStatus] = useState('idle');
  const [currentPhase, setCurrentPhase] = useState(0);
  const [feedbackText, setFeedbackText] = useState('');
  const [showFeedback, setShowFeedback] = useState(false);
  const eventsEndRef = useRef(null);
  const hasStarted = useRef(false);

  const scrollToBottom = useCallback(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => { scrollToBottom(); }, [state.workflowEvents, scrollToBottom]);

  useEffect(() => {
    if (state.workflowStatus !== 'running' || hasStarted.current) return;
    hasStarted.current = true;
    setStatus('running');

    runWorkflow(state.requirements, state.solutionType, (ev) => {
      dispatch({ type: 'WORKFLOW_EVENT', payload: ev });

      switch (ev.type) {
        case 'phase_start':
          setCurrentPhase(ev.phase);
          setShowFeedback(false);
          break;
        case 'agent_response':
          if (ev.ws) setWsRef(ev.ws);
          if (ev.phase === 1) dispatch({ type: 'SET_REPHRASED', payload: ev.content });
          if (ev.phase === 2) dispatch({ type: 'SET_TOPOLOGY', payload: ev.content });
          if (ev.phase === 3) dispatch({ type: 'SET_DEVICES', payload: ev.content });
          if (ev.phase === 6) dispatch({ type: 'SET_CLI_CONFIG', payload: ev.content });
          break;
        case 'topology_code_ready':
          if (ev.code) dispatch({ type: 'SET_REACT_CODE', payload: ev.code });
          break;
        case 'approval_request':
          setStatus('awaiting');
          if (ev.ws) setWsRef(ev.ws);
          break;
        case 'phase_approved':
          setStatus('running');
          break;
        case 'phase_revision':
          setStatus('running');
          setShowFeedback(false);
          break;
      }
    })
      .then((results) => {
        setStatus('complete');
        if (results.diagramUrl) {
          dispatch({ type: 'SET_DIAGRAM', payload: { url: results.diagramUrl, downloadUrl: results.diagramDownloadUrl } });
        }
        dispatch({ type: 'WORKFLOW_COMPLETE' });
        dispatch({
          type: 'SET_PROPOSED_DESIGN',
          payload: {
            summary: results.rephrased?.substring(0, 200) + '…',
            topology: { nodes: [], links: [] },
            bom: [],
          },
        });
      })
      .catch((err) => {
        setStatus('error');
        dispatch({ type: 'WORKFLOW_EVENT', payload: { type: 'error', message: err.message } });
        dispatch({ type: 'WORKFLOW_ERROR' });
      });
  }, [state.workflowStatus, state.requirements, state.solutionType, dispatch]);

  function handleApprove() {
    sendApproval(wsRef);
    dispatch({ type: 'WORKFLOW_EVENT', payload: { type: 'user_action', content: '✅ Approved' } });
    setStatus('running');
  }

  function handleRevise() {
    if (!feedbackText.trim()) return;
    sendRevision(wsRef, feedbackText.trim());
    dispatch({ type: 'WORKFLOW_EVENT', payload: { type: 'user_action', content: feedbackText.trim() } });
    setFeedbackText('');
    setShowFeedback(false);
    setStatus('running');
  }

  if (state.workflowStatus === 'idle' && !state.rephrasedPrompt) {
    return (
      <div className="p-8 text-center mt-20">
        <span className="material-symbols-outlined text-6xl text-outline mb-4">info</span>
        <h2 className="text-xl font-bold text-on-surface mb-2">No design generated yet</h2>
        <p className="text-on-surface-variant mb-6">Please fill out the requirements form first.</p>
        <button onClick={() => navigate('/requirements')} className="px-6 py-3 bg-primary text-on-primary font-bold rounded-lg">
          Go to Requirements
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full overflow-hidden">
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="p-6 pb-0">
          <div className="flex items-center gap-2 text-primary mb-2">
            <span className="material-symbols-outlined text-sm">auto_awesome</span>
            <span className="text-xs font-[family-name:var(--font-mono)] uppercase tracking-[0.2em]">AI Workflow</span>
          </div>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold font-[family-name:var(--font-headline)] text-on-surface tracking-tight">
                Network Design Pipeline
              </h1>
              <p className="text-on-surface-variant text-sm mt-1">
                {status === 'running' && '⏳ Processing…'}
                {status === 'awaiting' && '✋ Awaiting your approval'}
                {status === 'complete' && '✅ Workflow complete'}
                {status === 'error' && '❌ Error occurred'}
                {status === 'idle' && 'Ready'}
              </p>
            </div>
            {status === 'complete' && (
              <div className="flex gap-3">
                <button onClick={() => navigate('/bom')}
                  className="px-4 py-2 bg-primary text-on-primary font-bold rounded-lg hover:brightness-110 transition-all flex items-center gap-2 text-sm">
                  <span className="material-symbols-outlined text-lg">receipt_long</span>
                  View BOM
                </button>
                <button onClick={() => navigate('/interactive-topology')}
                  className="px-4 py-2 bg-tertiary text-on-tertiary font-bold rounded-lg hover:brightness-110 transition-all flex items-center gap-2 text-sm">
                  <span className="material-symbols-outlined text-lg">hub</span>
                  Interactive Topology
                </button>
                <button onClick={() => navigate('/deployment')}
                  className="px-4 py-2 bg-primary text-on-primary font-bold rounded-lg hover:brightness-110 transition-all flex items-center gap-2 text-sm">
                  Deployment
                  <span className="material-symbols-outlined text-lg">arrow_forward</span>
                </button>
              </div>
            )}
          </div>
        </header>

        {/* Phase progress bar — 6 phases */}
        <div className="px-6 py-4 flex gap-2">
          {['Prompt Rephrasing', 'Topology Design', 'Device Selection', 'Topology Diagram', 'React Topology', 'CLI Config'].map((name, i) => {
            const phaseNum = i + 1;
            const isActive = currentPhase === phaseNum;
            const isPast = currentPhase > phaseNum;
            return (
              <div key={i} className={`flex-1 h-1.5 rounded-full transition-all duration-500 ${
                isPast ? 'bg-tertiary' : isActive ? 'bg-primary animate-pulse' : 'bg-surface-container-high'
              }`} title={name} />
            );
          })}
        </div>

        {/* Events stream */}
        <div className="flex-1 overflow-y-auto px-6 pb-6 space-y-3 custom-scrollbar">
          {state.workflowEvents.map((ev, i) => (
            <EventCard key={i} event={ev} />
          ))}

          {status === 'awaiting' && (
            <div className="bg-tertiary/5 border border-tertiary/30 rounded-xl p-5 text-center animate-in fade-in">
              <h4 className="text-sm font-bold text-tertiary mb-3">
                ✋ Phase {currentPhase} Complete — Review & Approve
              </h4>
              <div className="flex gap-3 justify-center">
                <button onClick={handleApprove}
                  className="px-5 py-2 bg-tertiary text-on-tertiary font-bold rounded-lg hover:brightness-110 transition-all text-sm">
                  ✅ Approve & Continue
                </button>
                <button onClick={() => setShowFeedback(true)}
                  className="px-5 py-2 bg-surface-container-high border border-outline-variant/30 text-on-surface font-medium rounded-lg hover:border-primary/50 transition-all text-sm">
                  ✏️ Request Changes
                </button>
              </div>
              {showFeedback && (
                <div className="mt-4 flex gap-2">
                  <input value={feedbackText} onChange={e => setFeedbackText(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleRevise()}
                    className="flex-1 px-4 py-2 bg-surface-container-low border border-outline-variant/30 rounded-lg text-sm text-on-surface placeholder:text-outline/50 focus:ring-1 focus:ring-primary"
                    placeholder="Describe the changes you want…" autoFocus />
                  <button onClick={handleRevise}
                    className="px-4 py-2 bg-primary text-on-primary font-bold rounded-lg text-sm">Send</button>
                </div>
              )}
            </div>
          )}

          {status === 'running' && (
            <div className="flex items-center gap-3 text-on-surface-variant text-sm py-2">
              <div className="flex gap-1">
                <span className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{animationDelay: '0s'}} />
                <span className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{animationDelay: '0.15s'}} />
                <span className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{animationDelay: '0.3s'}} />
              </div>
              Agent is thinking…
            </div>
          )}

          <div ref={eventsEndRef} />
        </div>
      </div>

      <ChatbotSidebar />
    </div>
  );
}


function EventCard({ event }) {
  const [open, setOpen] = useState(false);
  const ev = event;

  switch (ev.type) {
    case 'user_echo':
      return (
        <div className="flex justify-end">
          <div className="bg-surface-container-high rounded-xl rounded-tr-none px-4 py-3 text-sm max-w-[80%]">
            {ev.content}
          </div>
        </div>
      );

    case 'phase_start':
      return (
        <div className="flex justify-center py-2">
          <div className="px-5 py-2 rounded-full text-xs font-bold uppercase tracking-wider bg-primary/10 border border-primary/30 text-primary">
            {ev.phase === 'diagram' ? ev.name : ev.phase === 'topology_validate' ? ev.name : `Phase ${ev.phase}: ${ev.name}`} {ev.iteration > 1 ? `(revision ${ev.iteration})` : ''}
          </div>
        </div>
      );

    case 'agent_input':
      return (
        <div className="flex items-center gap-2 text-xs text-on-surface-variant py-1">
          <span className="material-symbols-outlined text-primary text-sm">psychology</span>
          <span>Agent <strong className="text-on-surface">{ev.agent}</strong> processing…</span>
          <span className="text-outline text-[10px]">{ev.model}</span>
        </div>
      );

    case 'tool_call':
      return (
        <div className="border border-yellow-500/20 bg-yellow-500/5 rounded-xl overflow-hidden">
          <button onClick={() => setOpen(!open)}
            className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-yellow-500/5 transition-colors">
            <span className="material-symbols-outlined text-yellow-400 text-lg">build</span>
            <span className="font-medium text-on-surface flex-1">Tool: {ev.tool_name}</span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-yellow-500/20 text-yellow-400 font-medium">call</span>
            <span className="text-outline text-sm">{open ? '▾' : '▸'}</span>
          </button>
          {open && (
            <div className="px-4 pb-3 text-xs text-on-surface-variant">
              <pre className="bg-surface-container rounded-lg p-3 overflow-x-auto font-[family-name:var(--font-mono)]">
                {JSON.stringify(ev.tool_kwargs, null, 2)}
              </pre>
            </div>
          )}
        </div>
      );

    case 'rag_result': {
      const toolLabel = ev.tool_name === 'search_product_specs'
        ? 'Product Search'
        : ev.tool_name === 'search_across_products'
          ? 'Cross-Product Search'
          : 'RAG Search';
      return (
        <div className="border border-purple-400/20 bg-purple-500/5 rounded-xl overflow-hidden">
          <button onClick={() => setOpen(!open)}
            className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-purple-500/5 transition-colors">
            <span className="material-symbols-outlined text-purple-400 text-lg">library_books</span>
            <span className="font-medium text-on-surface flex-1">{toolLabel}: {ev.total} chunks retrieved</span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-400 font-medium">retrieval</span>
            <span className="text-outline text-sm">{open ? '▾' : '▸'}</span>
          </button>
          {open && (
            <div className="px-4 pb-3 space-y-2 max-h-64 overflow-y-auto custom-scrollbar">
              {(ev.chunks || []).map((c, i) => (
                <div key={i} className="bg-surface-container rounded-lg p-3 border-l-2 border-purple-400/40">
                  <div className="text-[10px] font-bold text-purple-400 mb-1">
                    Chunk {c.index} — score: {c.score?.toFixed(4)} — {c.source}
                  </div>
                  <div className="text-xs text-on-surface-variant leading-relaxed">
                    {c.text}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    case 'tool_result': {
      const isCatalog = ev.tool_name === 'list_available_products';
      return (
        <div className={`border rounded-xl overflow-hidden ${isCatalog ? 'border-cyan-500/20 bg-cyan-500/5' : 'border-outline-variant/10'}`}>
          <button onClick={() => setOpen(!open)}
            className="w-full flex items-center gap-2 px-4 py-2 text-xs text-left hover:bg-surface-container-high/30 transition-colors">
            <span className="material-symbols-outlined text-yellow-400 text-sm">
              {isCatalog ? 'inventory_2' : 'output'}
            </span>
            <span className="text-on-surface-variant flex-1">
              {isCatalog ? '📦 Product Catalog' : `Tool result: ${ev.tool_name}`} ({ev.output?.length || 0} chars)
            </span>
            <span className="text-outline text-sm">{open ? '▾' : '▸'}</span>
          </button>
          {open && (
            <div className="px-4 pb-3 text-xs text-on-surface-variant">
              <pre className="bg-surface-container rounded-lg p-3 overflow-x-auto font-[family-name:var(--font-mono)] whitespace-pre-wrap">
                {ev.output}
              </pre>
            </div>
          )}
        </div>
      );
    }

    case 'config_rag_result':
      return (
        <div className="border border-emerald-500/20 bg-emerald-500/5 rounded-xl overflow-hidden">
          <button onClick={() => setOpen(!open)}
            className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-emerald-500/5 transition-colors">
            <span className="material-symbols-outlined text-emerald-400 text-lg">terminal</span>
            <span className="font-medium text-on-surface flex-1">Config Guide Search: {ev.total_chars} chars retrieved</span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-medium">CLI reference</span>
            <span className="text-outline text-sm">{open ? '▾' : '▸'}</span>
          </button>
          {open && (
            <div className="px-4 pb-3 text-xs text-on-surface-variant max-h-64 overflow-y-auto custom-scrollbar">
              <pre className="whitespace-pre-wrap font-[family-name:var(--font-mono)]">{ev.output}</pre>
            </div>
          )}
        </div>
      );

    case 'agent_response':
      return (
        <div className="bg-surface-container-low border border-outline-variant/15 rounded-xl rounded-tl-none px-5 py-4 text-sm md-content max-w-[95%]"
          dangerouslySetInnerHTML={{ __html: renderMd(ev.content) }} />
      );

    case 'phase_approved':
      return (
        <div className="flex justify-center py-1">
          <span className="text-xs font-medium text-tertiary bg-tertiary/10 px-4 py-1.5 rounded-full">
            ✅ Phase {ev.phase} approved
          </span>
        </div>
      );

    case 'user_action':
      return (
        <div className="flex justify-end">
          <div className="bg-surface-container-high rounded-xl rounded-tr-none px-4 py-2.5 text-sm max-w-[80%]">
            {ev.content}
          </div>
        </div>
      );

    case 'workflow_complete':
      return (
        <div className="flex justify-center py-2">
          <div className="px-5 py-2 rounded-full text-xs font-bold bg-tertiary/10 border border-tertiary/30 text-tertiary">
            ✅ Workflow Complete
          </div>
        </div>
      );

    case 'error':
      return (
        <div className="bg-error/10 border border-error/30 rounded-xl px-4 py-3 text-sm text-error">
          ❌ {ev.message}
        </div>
      );

    case 'diagram_ready':
      return (
        <div className="border border-tertiary/30 bg-tertiary/5 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-tertiary/15">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-tertiary text-lg">schema</span>
              <span className="text-sm font-bold text-on-surface">Network Topology Diagram</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-tertiary/20 text-tertiary font-medium">SVG</span>
            </div>
            <a href={ev.download_url || ev.url} download={ev.filename || 'topology.svg'}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-tertiary/15 text-tertiary text-xs font-bold rounded-lg hover:bg-tertiary/25 transition-colors">
              <span className="material-symbols-outlined text-sm">download</span>
              Download SVG
            </a>
          </div>
          <div className="p-4 bg-white rounded-b-xl flex items-center justify-center">
            <img src={ev.url} alt="Network Topology Diagram" className="max-w-full max-h-[600px] object-contain" />
          </div>
        </div>
      );

    case 'diagram_error':
      return (
        <div className="bg-error/10 border border-error/30 rounded-xl px-4 py-3 text-sm text-error flex items-center gap-2">
          <span className="material-symbols-outlined text-sm">warning</span>
          Diagram rendering failed: {ev.message}
        </div>
      );

    case 'topology_code_ready':
      return (
        <div className="border border-cyan-500/30 bg-cyan-500/5 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-cyan-500/15">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-cyan-400 text-lg">hub</span>
              <span className="text-sm font-bold text-on-surface">Interactive Topology</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-400 font-medium">React Flow</span>
            </div>
            <button
              onClick={() => window.dispatchEvent(new CustomEvent('navigate', { detail: '/interactive-topology' }))}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-cyan-500/15 text-cyan-400 text-xs font-bold rounded-lg hover:bg-cyan-500/25 transition-colors">
              <span className="material-symbols-outlined text-sm">open_in_new</span>
              Open Viewer
            </button>
          </div>
          <div className="px-5 py-3 text-xs text-on-surface-variant">
            Interactive topology generated successfully. Click "Open Viewer" to pan, zoom, and explore the network diagram.
          </div>
        </div>
      );

    case 'topology_code_error':
      return (
        <div className="bg-error/10 border border-error/30 rounded-xl px-4 py-3 text-sm text-error flex items-center gap-2">
          <span className="material-symbols-outlined text-sm">warning</span>
          Topology validation failed: {ev.message}
        </div>
      );

    default:
      return null;
  }
}
