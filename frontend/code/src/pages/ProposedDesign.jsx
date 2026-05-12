/**
 * ProposedDesign — AI Workflow with streaming intermediate steps
 *
 * On mount (after Requirements submit), connects via WebSocket and
 * runs the 3-phase workflow. Shows:
 * - Phase banners with progress
 * - Intermediate steps (agent thinking, tool calls, RAG chunks)
 * - Agent responses with markdown rendering
 * - Approval/revision UI between phases
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../context/ProjectContext';
import { runWorkflow, sendApproval, sendRevision, sendChatMessage } from '../services/api';
import { marked } from 'marked';

marked.setOptions({ gfm: true, breaks: true });

function renderMd(text) {
  if (!text) return '';
  return marked.parse(text);
}

export default function ProposedDesign() {
  const navigate = useNavigate();
  const { state, dispatch } = useProject();
  const [events, setEvents] = useState([]);
  const [wsRef, setWsRef] = useState(null);
  const [status, setStatus] = useState('idle'); // idle | running | awaiting | complete | error
  const [currentPhase, setCurrentPhase] = useState(0);
  const [feedbackText, setFeedbackText] = useState('');
  const [showFeedback, setShowFeedback] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [sending, setSending] = useState(false);
  const eventsEndRef = useRef(null);
  const hasStarted = useRef(false);

  const scrollToBottom = useCallback(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => { scrollToBottom(); }, [events, scrollToBottom]);

  // Start workflow on mount if flagged
  useEffect(() => {
    if (state.workflowStatus !== 'running' || hasStarted.current) return;
    hasStarted.current = true;
    setStatus('running');
    setEvents([]);

    runWorkflow(state.requirements, state.solutionType, (ev) => {
      setEvents(prev => [...prev, ev]);

      switch (ev.type) {
        case 'phase_start':
          setCurrentPhase(ev.phase);
          setShowFeedback(false);
          break;
        case 'agent_response':
          if (ev.ws) setWsRef(ev.ws);
          // Store per-phase result
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
        dispatch({ type: 'SET_REPHRASED', payload: results.rephrased });
        dispatch({ type: 'SET_TOPOLOGY', payload: results.topology });
        dispatch({ type: 'SET_DEVICES', payload: results.devices });
        if (results.diagramUrl) {
          dispatch({ type: 'SET_DIAGRAM', payload: { url: results.diagramUrl, code: results.plantumlCode } });
        }
        dispatch({ type: 'WORKFLOW_COMPLETE' });
        // Build legacy proposedDesign for BOM page
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
        setEvents(prev => [...prev, { type: 'error', message: err.message }]);
        dispatch({ type: 'WORKFLOW_ERROR' });
      });
  }, [state.workflowStatus, state.requirements, state.solutionType, dispatch]);

  function handleApprove() {
    sendApproval(wsRef);
    setEvents(prev => [...prev, { type: 'user_action', content: '✅ Approved' }]);
    setStatus('running');
  }

  function handleRevise() {
    if (!feedbackText.trim()) return;
    sendRevision(wsRef, feedbackText.trim());
    setEvents(prev => [...prev, { type: 'user_action', content: feedbackText.trim() }]);
    setFeedbackText('');
    setShowFeedback(false);
    setStatus('running');
  }

  async function handleChat(e) {
    e.preventDefault();
    if (!chatInput.trim()) return;
    setSending(true);
    dispatch({ type: 'ADD_CHAT_MESSAGE', payload: { role: 'user', content: chatInput, timestamp: new Date().toISOString() } });
    try {
      const res = await sendChatMessage(chatInput, state.chatHistory);
      dispatch({ type: 'ADD_CHAT_MESSAGE', payload: res });
    } catch (err) { console.error(err); }
    setChatInput('');
    setSending(false);
  }

  // If no workflow started and no previous results, redirect
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
      {/* Left: Workflow Event Stream */}
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
                <button onClick={() => navigate('/deployment')}
                  className="px-4 py-2 bg-primary text-on-primary font-bold rounded-lg hover:brightness-110 transition-all flex items-center gap-2 text-sm">
                  Deployment
                  <span className="material-symbols-outlined text-lg">arrow_forward</span>
                </button>
              </div>
            )}
          </div>
        </header>

        {/* Phase progress bar */}
        <div className="px-6 py-4 flex gap-2">
          {['Prompt Rephrasing', 'Topology Design', 'Device Selection', 'Topology Diagram'].map((name, i) => (
            <div key={i} className={`flex-1 h-1.5 rounded-full transition-all duration-500 ${
              currentPhase > i + 1 ? 'bg-tertiary' : currentPhase === i + 1 ? 'bg-primary animate-pulse' : 'bg-surface-container-high'
            }`} title={name} />
          ))}
        </div>

        {/* Events stream */}
        <div className="flex-1 overflow-y-auto px-6 pb-6 space-y-3 custom-scrollbar">
          {events.map((ev, i) => (
            <EventCard key={i} event={ev} />
          ))}

          {/* Approval UI */}
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

          {/* Loading indicator */}
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

      {/* Right: Copilot Chat */}
      <aside className="w-96 border-l border-outline-variant/15 flex flex-col bg-surface-dim">
        <div className="p-4 border-b border-outline-variant/10 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
            <span className="material-symbols-outlined text-primary">smart_toy</span>
          </div>
          <div>
            <div className="text-sm font-bold text-on-surface">Design Copilot</div>
            <div className="text-xs text-on-surface-variant">Ask about your network design</div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
          <div className="bg-surface-container-low rounded-lg p-3 border border-outline-variant/10">
            <p className="text-xs text-on-surface-variant italic">
              ✅ Your requirements have been loaded. Ask me anything about your design, or request changes.
            </p>
          </div>
          {state.chatHistory.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] rounded-lg px-4 py-3 text-sm ${
                msg.role === 'user'
                  ? 'bg-surface-container-high text-on-surface rounded-tr-none'
                  : 'bg-surface-container-low border border-outline-variant/10 text-on-surface rounded-tl-none md-content'
              }`}
                dangerouslySetInnerHTML={msg.role !== 'user' ? { __html: renderMd(msg.content) } : undefined}
              >
                {msg.role === 'user' ? msg.content : undefined}
              </div>
            </div>
          ))}
        </div>

        <form onSubmit={handleChat} className="p-4 border-t border-outline-variant/10">
          <div className="flex gap-2">
            <input value={chatInput} onChange={e => setChatInput(e.target.value)} disabled={sending}
              className="flex-1 bg-surface-container-low border border-outline-variant/20 rounded-lg px-4 py-2.5 text-sm text-on-surface placeholder:text-outline/50 focus:ring-1 focus:ring-primary"
              placeholder="Ask about your design…" />
            <button type="submit" disabled={sending}
              className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center text-on-primary hover:brightness-110 transition-all disabled:opacity-50">
              <span className="material-symbols-outlined text-lg">send</span>
            </button>
          </div>
        </form>
      </aside>
    </div>
  );
}


/* ─── Event Card Component ─── */
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
            Phase {ev.phase}: {ev.name} {ev.iteration > 1 ? `(revision ${ev.iteration})` : ''}
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

    case 'rag_result':
      return (
        <div className="border border-purple-400/20 bg-purple-500/5 rounded-xl overflow-hidden">
          <button onClick={() => setOpen(!open)}
            className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-purple-500/5 transition-colors">
            <span className="material-symbols-outlined text-purple-400 text-lg">library_books</span>
            <span className="font-medium text-on-surface flex-1">RAG: {ev.total} chunks retrieved</span>
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

    case 'tool_result':
      return (
        <div className="flex items-center gap-2 text-xs text-on-surface-variant py-1">
          <span className="material-symbols-outlined text-yellow-400 text-sm">output</span>
          Tool result: {ev.tool_name} ({ev.output?.length || 0} chars)
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
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-tertiary/20 text-tertiary font-medium">PlantUML</span>
            </div>
            <a href={ev.url} download={ev.filename || 'topology.png'}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-tertiary/15 text-tertiary text-xs font-bold rounded-lg hover:bg-tertiary/25 transition-colors">
              <span className="material-symbols-outlined text-sm">download</span>
              Download PNG
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

    default:
      return null;
  }
}
