import { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { useProject } from '../context/ProjectContext';
import { sendChatMessage } from '../services/api';
import { marked } from 'marked';
import katex from 'katex';
import 'katex/dist/katex.min.css';

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

export default function ChatbotSidebar() {
  const { state, dispatch } = useProject();
  const location = useLocation();
  const [chatInput, setChatInput] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.chatHistory, sending]);

  async function handleChat(e) {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const messageToSend = chatInput.trim();

    let screenContext = '';
    if (location.pathname === '/interactive-topology' && state.reactCode) {
      screenContext = `SYSTEM CONTEXT: The user is currently viewing the Interactive Topology screen. The raw React code rendering the diagram they see is:\n\n${state.reactCode}`;
    } else if (location.pathname === '/design') {
      screenContext = `SYSTEM CONTEXT: The user is currently on the AI Workflow Design pipeline. Current outputs:\nRephrased Prompt: ${state.rephrasedPrompt || 'None'}\nTopology Design: ${state.topologyDesign || 'None'}\nDevice Selection: ${state.deviceSelection || 'None'}`;
    } else if (location.pathname === '/bom') {
      screenContext = `SYSTEM CONTEXT: The user is viewing the Bill of Materials (BOM) screen. Devices: ${state.deviceSelection || 'None'}`;
    }

    setChatInput('');
    setSending(true);

    dispatch({ type: 'ADD_CHAT_MESSAGE', payload: { role: 'user', content: messageToSend, timestamp: new Date().toISOString() } });

    try {
      const res = await sendChatMessage(messageToSend, state.chatHistory, screenContext);
      dispatch({ type: 'ADD_CHAT_MESSAGE', payload: res });
    } catch (err) {
      console.error(err);
    }
    setSending(false);
  }

  return (
    <aside className="w-96 border-l border-outline-variant/15 flex flex-col bg-surface-dim h-full">
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
            <div
              className={`max-w-[85%] rounded-lg px-4 py-3 text-sm ${
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

        {sending && (
          <div className="flex justify-start">
            <div className="bg-surface-container-low border border-outline-variant/10 rounded-lg rounded-tl-none px-4 py-3 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0s' }} />
              <span className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0.15s' }} />
              <span className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0.3s' }} />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleChat} className="p-4 border-t border-outline-variant/10">
        <div className="flex gap-2">
          <input
            value={chatInput}
            onChange={e => setChatInput(e.target.value)}
            disabled={sending}
            className="flex-1 bg-surface-container-low border border-outline-variant/20 rounded-lg px-4 py-2.5 text-sm text-on-surface placeholder:text-outline/50 focus:ring-1 focus:ring-primary"
            placeholder="Ask about your design…"
          />
          <button
            type="submit"
            disabled={sending}
            className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center text-on-primary hover:brightness-110 transition-all disabled:opacity-50"
          >
            <span className="material-symbols-outlined text-lg">send</span>
          </button>
        </div>
      </form>
    </aside>
  );
}
