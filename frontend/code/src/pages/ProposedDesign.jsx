/**
 * ProposedDesign — Auto-generated after form submission
 * 
 * Shows: visual topology placeholder, plain-English summary,
 * and the Grounded Design Copilot chat for refinements.
 * The AI team will replace the static topology with real generated diagrams.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../context/ProjectContext';
import { sendChatMessage } from '../services/api';

export default function ProposedDesign() {
  const navigate = useNavigate();
  const { state, dispatch } = useProject();
  const design = state.proposedDesign;
  const [chatInput, setChatInput] = useState('');
  const [sending, setSending] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  // Send a message to the Grounded Design Copilot
  async function handleSendChat(e) {
    e.preventDefault();
    if (!chatInput.trim()) return;
    setSending(true);

    // Add user message to history
    dispatch({ type: 'ADD_CHAT_MESSAGE', payload: { role: 'user', content: chatInput, timestamp: new Date().toISOString() } });

    try {
      const response = await sendChatMessage(chatInput, state.chatHistory);
      dispatch({ type: 'ADD_CHAT_MESSAGE', payload: response });
    } catch (err) {
      console.error('Chat error:', err);
    }

    setChatInput('');
    setSending(false);
  }

  if (!design) {
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
      {/* Left: Design View */}
      <div className="flex-1 p-8 overflow-y-auto custom-scrollbar">
        <header className="mb-8">
          <div className="flex items-center gap-2 text-primary mb-2">
            <span className="material-symbols-outlined text-sm">auto_awesome</span>
            <span className="text-xs font-[family-name:var(--font-mono)] uppercase tracking-[0.2em]">AI Generated</span>
          </div>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold font-[family-name:var(--font-headline)] text-on-surface tracking-tight">
                Proposed Logical Design
              </h1>
              <p className="text-on-surface-variant mt-2">{design.summary}</p>
            </div>
            <button 
              onClick={() => navigate('/topology')}
              className="mt-1 px-4 py-2 bg-surface-container-high border border-outline-variant/30 text-on-surface-variant text-sm font-medium rounded-lg hover:text-primary hover:border-primary/50 transition-all flex items-center gap-2 shrink-0"
            >
              <span className="material-symbols-outlined text-lg">account_tree</span>
              Detailed Topology
            </button>
          </div>
        </header>

        {/* Visible TODO for frontend integration — height increased to balance layout */}
        <section className="bg-surface-container-low rounded-xl border border-outline-variant/15 min-h-[450px] mb-8 flex flex-col items-center justify-center text-center">
          <div className="bg-surface-container-high px-6 py-3 rounded-lg border border-outline-variant/30 font-mono text-sm text-primary/80 shadow-sm">
            TODO: // AI-GENERATED TOPOLOGY COMPONENT GOES HERE
          </div>
          <p className="text-xs text-on-surface-variant/40 mt-6 uppercase tracking-[0.3em] font-medium">Logical Design Canvas</p>
        </section>

        {/* Action Buttons */}
        <div className="flex gap-4">
          <button onClick={() => navigate('/bom')} className="px-6 py-3 bg-primary text-on-primary font-bold rounded-lg hover:brightness-110 transition-all flex items-center gap-2">
            <span className="material-symbols-outlined">receipt_long</span>
            View Bill of Materials
          </button>
          <button onClick={() => navigate('/requirements')} className="px-6 py-3 border border-outline-variant/30 text-on-surface font-medium rounded-lg hover:bg-surface-container-high transition-all">
            Modify Requirements
          </button>
          <button onClick={() => navigate('/deployment')} className="px-6 py-3 bg-primary text-on-primary font-bold rounded-lg hover:brightness-110 transition-all flex items-center gap-2 ml-auto">
            Proceed to Deployment
            <span className="material-symbols-outlined">arrow_forward</span>
          </button>
        </div>
      </div>

      {/* Right: Grounded Design Copilot Chat */}
      <aside className="w-96 border-l border-outline-variant/15 flex flex-col bg-surface-dim relative">
        {/* Chat Header */}
        <div className="p-4 border-b border-outline-variant/10 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
              <span className="material-symbols-outlined text-primary">smart_toy</span>
            </div>
            <div>
              <div className="text-sm font-bold text-on-surface">Grounded Design Copilot</div>
              <div className="text-xs text-on-surface-variant">Ask about your network design</div>
            </div>
          </div>
          <button 
            onClick={() => setShowHistory(!showHistory)}
            className={`p-2 rounded-lg transition-colors ${showHistory ? 'bg-primary text-on-primary' : 'text-on-surface-variant hover:bg-surface-container-high'}`}
            title="Chat History"
          >
            <span className="material-symbols-outlined text-xl">history</span>
          </button>
        </div>

        {/* History Panel (Overlay) */}
        {showHistory && (
          <div className="absolute inset-0 top-[69px] z-10 bg-surface-dim flex flex-col animate-in fade-in slide-in-from-right-4 duration-300">
            <div className="p-4 border-b border-outline-variant/10 flex items-center justify-between bg-surface-container-low/50">
              <span className="text-xs font-bold text-outline uppercase tracking-widest">Previous Sessions</span>
              <button onClick={() => setShowHistory(false)} className="text-outline hover:text-on-surface">
                <span className="material-symbols-outlined text-sm">close</span>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {/* TODO: [BACKEND TEAM] 
                  Fetch actual chat sessions for this project from the database.
                  Each session should have a timestamp and a summary/title.
              */}
              {[
                { id: 1, title: 'Initial Design Discussion', date: '2 hours ago' },
                { id: 2, title: 'VLAN Configuration Help', date: 'Yesterday' },
                { id: 3, title: 'BOM Review Session', date: 'Oct 24, 2026' },
              ].map(session => (
                <button key={session.id} className="w-full text-left p-3 rounded-lg hover:bg-surface-container-high transition-colors group">
                  <div className="text-sm text-on-surface font-medium truncate">{session.title}</div>
                  <div className="text-[10px] text-on-surface-variant mt-1">{session.date}</div>
                </button>
              ))}
            </div>
            <div className="p-4 border-t border-outline-variant/10">
              <button className="w-full py-2 bg-surface-container-highest border border-outline-variant/30 text-on-surface text-xs font-bold rounded-lg hover:bg-primary/10 hover:text-primary hover:border-primary/50 transition-all">
                + NEW CHAT SESSION
              </button>
            </div>
          </div>
        )}

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Auto-context message */}
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
                  : 'bg-surface-container-low border border-outline-variant/10 text-on-surface rounded-tl-none'
              }`}>
                {msg.content}
              </div>
            </div>
          ))}
        </div>

        {/* Chat Input */}
        <form onSubmit={handleSendChat} className="p-4 border-t border-outline-variant/10">
          <div className="flex gap-2">
            <input value={chatInput} onChange={e => setChatInput(e.target.value)} disabled={sending}
              className="flex-1 bg-surface-container-low border border-outline-variant/20 rounded-lg px-4 py-2.5 text-sm text-on-surface placeholder:text-outline/50 focus:ring-1 focus:ring-primary"
              placeholder="Ask about your design..." />
            <button type="submit" disabled={sending} className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center text-on-primary hover:brightness-110 transition-all disabled:opacity-50">
              <span className="material-symbols-outlined text-lg">send</span>
            </button>
          </div>
          <p className="text-[10px] text-on-surface-variant/50 mt-2 text-center">Only answers network & infrastructure questions</p>
        </form>
      </aside>
    </div>
  );
}
