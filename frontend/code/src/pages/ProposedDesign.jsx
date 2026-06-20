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
import { useState, useEffect, useRef, useMemo } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useProject } from "../context/ProjectContext";
import {
  runWorkflow,
  resumeWorkflow,
  sendApproval,
  sendRevision,
  sendChatMessage,
  getProjectConversation,
  getConversationMessages,
  getWorkflowState,
  getPersistentChatHistory,
  buildPromptFromRequirements,
} from "../services/api";
import { renderMd } from "../utils/renderMd";

const PHASE_LABELS = [
  "Prompt Rephrasing",
  "Topology Design",
  "Device Selection",
  "Topology Diagram",
  "CLI Config",
];
const statusStyles = {
  draft: "text-outline",
  designing: "text-primary",
  complete: "text-tertiary",
  deployed: "text-tertiary",
};

export default function ProposedDesign() {
  const navigate = useNavigate();
  const { projectId } = useParams();
  const [searchParams] = useSearchParams();
  const isFresh = searchParams.get("fresh") === "1";
  const { state, dispatch, loadProject } = useProject();
  const wsRef = useRef(null);
  const pendingApprovalRef = useRef(null);
  const [status, setStatus] = useState("idle"); // idle | running | awaiting | complete | error
  const [currentPhase, setCurrentPhase] = useState(0);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);
  const [feedbackText, setFeedbackText] = useState("");
  const [showFeedback, setShowFeedback] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [sending, setSending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [projectList, setProjectList] = useState([]);
  const eventsEndRef = useRef(null);

  const hasStarted = useRef(false);
  const retryCountRef = useRef(0);
  const MAX_RETRIES = 3;

  useEffect(() => {
    hasStarted.current = false;
    pendingApprovalRef.current = null;
    wsRef.current = null;
    setCurrentPhase(0);
    setStatus(state.workflowStatus === "complete" ? "complete" : "idle");
  }, [projectId]); // reset per project to avoid stale run guard

  const mergedTimeline = useMemo(() => {
    const seen = new Set();
    const events = state.workflowEvents
      .filter((ev) => {
        if (!ev.phase) return true;
        if (
          status === "running" ||
          status === "awaiting" ||
          status === "reconnecting"
        ) {
          return ev.phase <= currentPhase;
        }
        return true;
      })
      .filter((ev) => {
        const key =
          ev._id ||
          `${ev.type}|${ev.phase || ""}|${ev.tool_name || ""}|${ev.content || ""}|${typeof ev.tool_kwargs === "object" ? JSON.stringify(ev.tool_kwargs) : ev.tool_kwargs || ""}`;
        if (seen.has(key)) return false;
        seen.add(key);
        if (ev.type === "agent_response" && ev.content) {
          seen.add(`chat|assistant|${ev.content}`);
        }
        return true;
      })
      .map((ev) => ({ _kind: "event", ...ev }));

    const chats = state.chatHistory
      .filter((msg) => {
        const key = `chat|${msg.role}|${msg.content}`;
        if (seen.has(key)) return false;
        seen.add(key);
        // Hide raw React code from being rendered as a chat bubble
        if (
          msg.role === "assistant" &&
          msg.content &&
          msg.content.includes("import React") &&
          msg.content.includes("reactflow")
        ) {
          return false;
        }
        return true;
      })
      .map((msg) => ({
        _kind: "chat",
        ...msg,
        timestamp: msg.timestamp || null,
      }));

    const allItems = [...events, ...chats];
    
    // Inject the initial prompt
    if (state.requirements && !chats.some(c => c.content?.includes("Initial System Request:") || c.content?.includes("UserReq:"))) {
        const rawPrompt = buildPromptFromRequirements(state.requirements, state.solutionType);
        allItems.unshift({
            type: "user_echo",
            content: `**Initial System Request:**\n\n${rawPrompt}`,
            timestamp: new Date(0).toISOString() // Ensure it sorts to the top
        });
    }

    return allItems.sort((a, b) => {
      const ta = a.timestamp ? new Date(a.timestamp).getTime() : 0;
      const tb = b.timestamp ? new Date(b.timestamp).getTime() : 0;
      return ta - tb;
    });
  }, [state.workflowEvents, state.chatHistory, status, currentPhase]);

  useEffect(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [mergedTimeline]);

  // Sync progress bar with persisted workflow state
  useEffect(() => {
    if (state.workflowStatus === "complete") {
      setCurrentPhase(6);
    }
  }, [state.workflowStatus]);

  // Load project state on mount
  useEffect(() => {
    if (projectId && state.projectId !== projectId) {
      loadProject(projectId);
    }
  }, [projectId, state.projectId, loadProject]);

  // Load conversation history from API if project has past results
  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    setHistoryLoading(true);
    setHistoryError(null);
    (async () => {
      try {
        const persistent = await getPersistentChatHistory(
          projectId,
          state.conversationId || "default",
        );
        if (!cancelled && persistent?.conversation_messages?.length) {
          const persistedMessages = persistent.conversation_messages.map(
            (m) => ({
              role:
                String(m.role || "").toLowerCase() === "user"
                  ? "user"
                  : "assistant",
              content: m.content || "",
              timestamp:
                m.created_at || m.createdAt || m.timestamp || null,
            }),
          );
          dispatch({ type: "SET_CHAT_HISTORY", payload: persistedMessages });
          setHistoryLoading(false);
          return;
        }

        const conv = await getProjectConversation(projectId);
        if (cancelled) return;
        if (conv && conv.id !== state.conversationId) {
          dispatch({ type: "SET_CONVERSATION_ID", payload: conv.id });
        }
        const messages = conv ? await getConversationMessages(conv.id) : [];
        if (cancelled) return;
        if (messages.length) {
          const chatMsgs = messages.map((m) => ({
            role: m.role,
            content: m.content,
            timestamp: m.createdAt || null,
          }));
          dispatch({ type: "SET_CHAT_HISTORY", payload: chatMsgs });
        }
      } catch (err) {
        if (!cancelled) setHistoryError("Failed to load conversation history");
      } finally {
        if (!cancelled) setHistoryLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, state.conversationId, dispatch]);

  // Start workflow on mount if flagged
  useEffect(() => {
    if (state.workflowStatus !== "running" || hasStarted.current) return;
    hasStarted.current = true;

    let cancelled = false;
    (async () => {
      // Fetch completed phases from server
      const serverState = await getWorkflowState(projectId);
      if (cancelled) return;

      const completedPhases = !isFresh
        ? serverState?.completed_phases || []
        : [];

      // Dispatch results from server if any
      if (completedPhases.length > 0) {
        const existingApprovedPhases = new Set(
          state.workflowEvents
            .filter((ev) => ev.type === "phase_approved")
            .map((ev) => ev.phase),
        );
        const phaseEvents = [];
        for (const p of completedPhases) {
          if (p.phase === 1)
            dispatch({ type: "SET_REPHRASED", payload: p.output });
          else if (p.phase === 2)
            dispatch({ type: "SET_TOPOLOGY", payload: p.output });
          else if (p.phase === 3)
            dispatch({ type: "SET_DEVICES", payload: p.output });
          else if (p.phase === 5)
            dispatch({ type: "SET_CLI_CONFIG", payload: p.output });
          if (!existingApprovedPhases.has(p.phase)) {
            phaseEvents.push({ type: "phase_approved", phase: p.phase });
          }
        }
        phaseEvents.forEach((ev) =>
          dispatch({ type: "WORKFLOW_EVENT", payload: ev }),
        );
        // setStatus('running');
        //
        // runWorkflow(state.requirements, state.solutionType, (ev) => {
        //   dispatch({ type: 'WORKFLOW_EVENT', payload: ev });
        //
        //   switch (ev.type) {
        //     case 'phase_start':
        //       setCurrentPhase(ev.phase);
        //       setShowFeedback(false);
        //       break;
        //     case 'agent_response':
        //       if (ev.ws) setWsRef(ev.ws);
        //       if (ev.phase === 1) dispatch({ type: 'SET_REPHRASED', payload: ev.content });
        //       if (ev.phase === 2) dispatch({ type: 'SET_TOPOLOGY', payload: ev.content });
        //       if (ev.phase === 3) dispatch({ type: 'SET_DEVICES', payload: ev.content });
        //       break;
        //     case 'approval_request':
        //       setStatus('awaiting');
        //       if (ev.ws) setWsRef(ev.ws);
        //       break;
        //     case 'topology_code_ready':
        //       if (ev.code) {
        //         dispatch({ type: 'SET_REACT_CODE', payload: ev.code });
        //       }
        //       break;
        //     case 'phase_approved':
        //       setStatus('running');
        //       break;
        //     case 'phase_revision':
        //       setStatus('running');
        //       setShowFeedback(false);
        //       break;
      }

      // Sync progress bar with completed phases
      if (completedPhases.length > 0) {
        const phases = completedPhases.map((p) => p.phase);
        setCurrentPhase(Math.max(...phases) + 1);
      }

      // If all phases complete, stop here
      if (serverState?.status === "complete") {
        dispatch({ type: "WORKFLOW_COMPLETE" });
        setStatus("complete");
        return;
      }

      // Otherwise start/resume workflow for remaining phases
      setStatus("running");

      const handleEvent = (ev) => {
        dispatch({ type: "WORKFLOW_EVENT", payload: ev });
        switch (ev.type) {
          case "phase_start":
            setCurrentPhase(ev.phase);
            setShowFeedback(false);
            break;
          case "approval_request":
            setStatus("awaiting");
            wsRef.current = ev.ws;
            pendingApprovalRef.current = ev.approval || null;
            break;
          case "phase_approved":
            setStatus("running");
            pendingApprovalRef.current = null;
            break;
          case "workflow_complete":
            setStatus("complete");
            dispatch({ type: "WORKFLOW_COMPLETE" });
            pendingApprovalRef.current = null;
            break;
          case "phase_revision":
            setStatus("running");
            setShowFeedback(false);
            break;
          case "agent_response":
            if (ev.phase) {
              switch (ev.phase) {
                case 1:
                  dispatch({ type: "SET_REPHRASED", payload: ev.content });
                  break;
                case 2:
                  dispatch({ type: "SET_TOPOLOGY", payload: ev.content });
                  break;
                case 3:
                  dispatch({ type: "SET_DEVICES", payload: ev.content });
                  break;
                case 4:
                  dispatch({ type: "SET_REACT_CODE", payload: ev.content });
                  break;
                case 5:
                  dispatch({ type: "SET_CLI_CONFIG", payload: ev.content });
                  break;
              }
            }
            break;
          case "diagram_ready":
            dispatch({
              type: "SET_DIAGRAM",
              payload: { url: ev.payload?.url || ev.url, downloadUrl: ev.payload?.download_url || ev.download_url },
            });
            if (ev.data) dispatch({ type: "SET_REACT_CODE", payload: ev.data });
            break;
        }
      };

      const handleComplete = (results) => {
        setStatus("complete");
        if (results.rephrased)
          dispatch({ type: "SET_REPHRASED", payload: results.rephrased });
        if (results.topology)
          dispatch({ type: "SET_TOPOLOGY", payload: results.topology });
        if (results.devices)
          dispatch({ type: "SET_DEVICES", payload: results.devices });
        if (results.diagramUrl) {
          dispatch({
            type: "SET_DIAGRAM",
            payload: {
              url: results.diagramUrl,
              downloadUrl: results.diagramDownloadUrl,
            },
          });
        }
        if (results.diagramCode) {
          dispatch({ type: "SET_REACT_CODE", payload: results.diagramCode });
        }
        if (results.cliConfig) {
          dispatch({ type: "SET_CLI_CONFIG", payload: results.cliConfig });
        }
        dispatch({ type: "WORKFLOW_COMPLETE" });
        dispatch({
          type: "SET_PROPOSED_DESIGN",
          payload: {
            summary:
              (results.rephrased || state.rephrasedPrompt || "")?.substring(
                0,
                200,
              ) + "…",
            topology: { nodes: [], links: [] },
            bom: [],
          },
        });
      };

      const handleError = (err) => {
        setStatus("error");
        dispatch({
          type: "WORKFLOW_EVENT",
          payload: { type: "error", message: err.message },
        });
        dispatch({ type: "WORKFLOW_ERROR" });
      };

      if (completedPhases.length > 0) {
        resumeWorkflow(projectId, handleEvent)
          .then(handleComplete)
          .catch(handleError);
      } else {
        runWorkflow(
          projectId,
          state.requirements,
          state.solutionType,
          handleEvent,
          isFresh,
        )
          .then(handleComplete)
          .catch(handleError);
      }
    })();

    return () => {
      cancelled = true;
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
      wsRef.current = null;
      pendingApprovalRef.current = null;
    };
  }, [
    state.workflowStatus,
    state.requirements,
    state.solutionType,
    projectId,
    dispatch,
  ]);

  function retryWorkflow() {
    hasStarted.current = false;
    retryCountRef.current = 0;
    setStatus("running");
    dispatch({ type: "WORKFLOW_RESUME" });
  }

  function handleApprove() {
    sendApproval(wsRef.current, pendingApprovalRef.current || {});
    dispatch({
      type: "WORKFLOW_EVENT",
      payload: { type: "phase_approved", phase: currentPhase },
    });
    setStatus("running");
  }

  function handleRevise() {
    if (!feedbackText.trim()) return;
    sendRevision(
      wsRef.current,
      feedbackText.trim(),
      pendingApprovalRef.current || {},
    );
    dispatch({
      type: "WORKFLOW_EVENT",
      payload: { type: "user_action", content: `Requested changes: ${feedbackText.trim()}` },
    });
    setFeedbackText("");
    setShowFeedback(false);
    setStatus("running");
  }

  async function handleChat(e) {
    e.preventDefault();
    if (!chatInput.trim() || sending) return;

    const messageToSend = chatInput.trim();
    setChatInput("");
    setSending(true);

    dispatch({
      type: "ADD_CHAT_MESSAGE",
      payload: {
        role: "user",
        content: messageToSend,
        timestamp: new Date().toISOString(),
      },
    });

    let screenContext = `SYSTEM CONTEXT: User is in AI Workflow Design.`;
    screenContext += `\nCurrent phase: ${currentPhase || "unknown"} (${status}).`;
    screenContext += `\nRephrased Prompt: ${state.rephrasedPrompt || "None"}`;
    screenContext += `\nTopology Design: ${state.topologyDesign || "None"}`;
    screenContext += `\nDevice Selection: ${state.deviceSelection || "None"}`;
    screenContext += `\nCLI Config: ${state.cliConfig || "None"}`;

    try {
      const res = await sendChatMessage(
        messageToSend,
        state.chatHistory,
        screenContext,
        projectId,
        state.conversationId,
      );
      dispatch({ type: "ADD_CHAT_MESSAGE", payload: res });
    } catch (err) {
      dispatch({
        type: "ADD_CHAT_MESSAGE",
        payload: {
          role: "assistant",
          content: "Unable to reach chat service right now. Please try again.",
          timestamp: new Date().toISOString(),
        },
      });
    } finally {
      setSending(false);
    }
  }

  // If no workflow started and no previous results, redirect
  if (
    !projectId ||
    (state.workflowStatus === "idle" && !state.rephrasedPrompt)
  ) {
    return (
      <div className="p-8 text-center mt-20">
        <span className="material-symbols-outlined text-6xl text-outline mb-4">
          info
        </span>
        <h2 className="text-xl font-bold text-on-surface mb-2">
          No design generated yet
        </h2>
        <p className="text-on-surface-variant mb-6">
          Please fill out the requirements form first.
        </p>
        <button
          onClick={() =>
            navigate(projectId ? `/project/${projectId}/requirements` : "/")
          }
          className="px-6 py-3 bg-primary text-on-primary font-bold rounded-lg"
        >
          Go to Requirements
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: Recent Chats Sidebar */}
      <aside
        className={`${sidebarOpen ? "w-72" : "w-0"} transition-all duration-300 border-r border-outline-variant/15 f
lex flex-col bg-surface-dim overflow-hidden`}
      >
        <div className="p-4 border-b border-outline-variant/10">
          <button
            onClick={() => navigate("/project/new")}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-on-primary font-bold rou
nded-lg hover:brightness-110 transition-all text-sm"
          >
            <span className="material-symbols-outlined text-lg">add</span>
            New Chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
          {projectList.map((p) => {
            const active = p.id === projectId;
            const sClass = statusStyles[p.status] || "text-outline";
            const statusIcon =
              p.status === "complete"
                ? "check_circle"
                : p.status === "designing"
                  ? "pending"
                  : "draft";
            return (
              <button
                key={p.id}
                onClick={() => navigate(`/project/${p.id}`)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left text-sm transition-colors ${
                  active
                    ? "bg-primary/10 text-primary"
                    : "hover:bg-surface-container-high text-on-surface"
                }`}
              >
                <span className="material-symbols-outlined text-lg text-outline">
                  folder
                </span>
                <span className="flex-1 truncate font-medium">
                  {p.title || "Untitled"}
                </span>
                <span className={`material-symbols-outlined text-xs ${sClass}`}>
                  {statusIcon}
                </span>
              </button>
            );
          })}
          {projectList.length === 0 && (
            <p className="text-xs text-outline text-center py-8">
              No projects yet
            </p>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar with hamburger + header */}
        <header className="px-6 py-4 border-b border-outline-variant/10 flex items-center gap-4">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1 text-outline hover:text-primary transition-colors"
          >
            <span className="material-symbols-outlined">
              {sidebarOpen ? "menu_open" : "menu"}
            </span>
          </button>
          <div className="flex-1">
            <div className="flex items-center gap-2 text-primary">
              <span className="material-symbols-outlined text-sm">
                auto_awesome
              </span>
              <span className="text-xs font-[family-name:var(--font-mono)] uppercase tracking-[0.2em]">
                AI Workflow
              </span>
            </div>
            <div className="flex items-center gap-4">
              <h1 className="text-xl font-bold font-[family-name:var(--font-headline)] text-on-surface tracking-tight">
                {state.projectTitle || "Network Design Pipeline"}
              </h1>
              <span className="text-xs text-on-surface-variant">
                {status === "running" && "⏳ Processing…"}
                {status === "awaiting" && "✋ Awaiting your approval"}
                {status === "complete" && "✅ Complete"}
                {status === "error" && "❌ Connection lost"}
                {status === "reconnecting" && "🔄 Reconnecting…"}
                {status === "idle" && "Ready"}
              </span>
            </div>
          </div>
          {status === "complete" && (
            <div className="flex gap-2">
              <button
                onClick={() => navigate(`/project/${projectId}/bom`)}
                className="px-3 py-1.5 bg-primary text-on-primary font-bold rounded-lg hover:brightness-110 transition-all text-xs"
              >
                BOM
              </button>
              <button
                onClick={() => navigate(`/project/${projectId}/deployment`)}
                className="px-3 py-1.5 bg-primary text-on-primary font-bold rounded-lg hover:brightness-110 transition-all text-xs"
              >
                Deploy
              </button>
            </div>
          )}
        </header>

        {/* Phase progress bar */}
        <div className="px-6 py-3 flex gap-2">
          {PHASE_LABELS.map((name, i) => {
            const phaseNum = i + 1;
            const isPast = currentPhase > phaseNum;
            const isActive = currentPhase === phaseNum;
            return (
              <div
                key={i}
                className={`flex-1 h-1.5 rounded-full transition-all duration-500 ${
                  isPast
                    ? "bg-tertiary"
                    : isActive
                      ? "bg-primary animate-pulse"
                      : "bg-surface-container-high"
                }`}
                title={name}
              />
            );
          })}
        </div>

        {/* Completed phases summary */}
        {(status === "awaiting" || status === "running") &&
          currentPhase > 1 && (
            <div className="px-6 py-2 flex gap-2 flex-wrap items-center">
              {Array.from({ length: currentPhase - 1 }, (_, i) => (
                <div
                  key={i}
                  className="flex items-center gap-1.5 text-[11px] text-tertiary bg-tertiary/10 px-2.5 py-1 rounded-full"
                >
                  <span className="material-symbols-outlined text-xs">
                    check_circle
                  </span>
                  Phase {i + 1}: {PHASE_LABELS[i]}
                </div>
              ))}
              {status === "awaiting" && (
                <div className="flex items-center gap-1.5 text-[11px] text-primary bg-primary/12 px-2.5 py-1 rounded-full">
                  <span className="material-symbols-outlined text-xs">
                    pending
                  </span>
                  Phase {currentPhase}: {PHASE_LABELS[currentPhase - 1]}
                </div>
              )}
            </div>
          )}

        {/* Scrollable content area */}
        {/*         <div className="flex-1 overflow-y-auto px-6 pb-4 space-y-4 custom-scrollbar"> */}
        {/**/}
        {/* Phase Outputs as text bubbles */}
        {/*           {phaseOutputs.map(p => { */}
        {/*             if (!p.content) return null; */}
        {/*             if (p.isImage) { */}
        {/*               return ( */}
        {/*                 <div key={p.phase} className="max-w-[90%]"> */}
        {/*                   <div className="text-[10px] text-outline/50 uppercase tracking-wider mb-1 px-1">Phase {p.phase} — {p.label}</div> */}
        {/*                   <div className="bg-surface-container-low rounded-lg rounded-tl-none p-3 border border-outline-variant/10"> */}
        {/*                     <img src={p.content} alt={p.label} className="max-w-full max-h-[500px] object-contain rounded" /> */}
        {/*                   </div> */}
        {/*                 </div> */}
        {/*               ); */}
        {/*             } */}
        {/*             return ( */}
        {/*               <div key={p.phase} className="max-w-[90%]"> */}
        {/*                 <div className="text-[10px] text-outline/50 uppercase tracking-wider mb-1 px-1">Phase {p.phase} — {p.label}</div> */}
        {/*                 <div className="bg-surface-container-low rounded-lg rounded-tl-none px-4 py-3 text-sm md-content border border-outline-variant/10" */}
        {/*                   dangerouslySetInnerHTML={{ __html: renderMd(p.content) }} /> */}
        {/*               </div> */}
        {/*             ); */}
        {/*           })} */}
        {/**/}
        {/* Collapsible Event Stream */}
        {/*           {events.length > 0 && ( */}
        {/*             <div className="bg-surface-container-low rounded-xl border border-outline-variant/15 overflow-hidden"> */}
        {/*               <button onClick={() => setShowToolEvents(!showToolEvents)} */}
        {/*                 className="w-full flex items-center justify-between px-5 py-3 text-sm text-left hover:bg-surface-container-high/30 transition-colors"> */}
        {/*                 <div className="flex items-center gap-2"> */}
        {/*                   <span className="material-symbols-outlined text-outline text-lg">list_alt</span> */}
        {/*                   <span className="font-medium text-on-surface">Event Details</span> */}
        {/*                   <span className="text-[10px] px-2 py-0.5 rounded-full bg-outline/10 text-outline font-medium">{events.length}</span> */}
        {/*                 </div> */}
        {/*                 <span className="text-outline text-sm">{showToolEvents ? '▾' : '▸'}</span> */}
        {/*               </button> */}
        {/*               {showToolEvents && ( */}
        {/*                 <div className="px-5 py-3 space-y-3 max-h-96 overflow-y-auto custom-scrollbar"> */}
        {/*                   {events.map((ev, i) => ( */}
        {/*                     <EventCard key={i} event={ev} /> */}
        {/*                   ))} */}
        {/*                 </div> */}
        {/*               )} */}
        {/*             </div> */}
        {/*           )} */}
        {/* Interactive Topology View Button has been moved to the bottom
             of the event stream (inside the workflow_complete EventCard)
             for a more natural, chronological workflow UX. */}

        {/* Events stream */}
        <div className="flex-1 overflow-y-auto px-6 pb-6 space-y-3 custom-scrollbar">
          <div className="text-[11px] text-outline uppercase tracking-wider px-1">
            Workflow Chat
          </div>
          {/* Merged timeline — chat + events in chronological order */}
          {mergedTimeline.map((item, i) => {
            if (item._kind === "chat") {
              return (
                <div
                  key={`c-${i}`}
                  className={`flex ${item.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
                      item.role === "user"
                        ? "bg-primary/10 text-on-surface rounded-tr-none"
                        : "bg-surface-container-low border border-outline-variant/10 text-on-surface rounded-tl-none md-content"
                    }`}
                    dangerouslySetInnerHTML={{ __html: renderMd(item.content) }}
                  />
                </div>
              );
            }
            return <EventCard key={`e-${i}`} event={item} />;
          })}

          {/* Approval UI */}
          {status === "awaiting" && (
            <div className="bg-tertiary/5 border border-tertiary/30 rounded-xl p-5 text-center animate-in fade-in">
              <h4 className="text-sm font-bold text-tertiary mb-3">
                ✋ Phase {currentPhase} Complete — Review & Approve
              </h4>
              <div className="flex gap-3 justify-center">
                <button
                  onClick={handleApprove}
                  className="px-5 py-2 bg-tertiary text-on-tertiary font-bold rounded-lg hover:brightness-110 transition-all text-sm"
                >
                  ✅ Approve & Continue
                </button>
                <button
                  onClick={() => setShowFeedback(true)}
                  className="px-5 py-2 bg-surface-container-high border border-outline-variant/30 text-on-surface font-medium rounded-lg hover:border-primary/50 transition-all text-sm"
                >
                  ✏️ Request Changes
                </button>
              </div>
              {showFeedback && (
                <div className="mt-4 flex gap-2">
                  <input
                    value={feedbackText}
                    onChange={(e) => setFeedbackText(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleRevise()}
                    className="flex-1 px-4 py-2 bg-surface-container-low border border-outline-variant/30 rounded-lg text-sm text-on-surface placeholder:text-outline/50 focus:ring-1 focus:ring-primary"
                    placeholder="Describe the changes you want…"
                    autoFocus
                  />
                  <button
                    onClick={handleRevise}
                    className="px-4 py-2 bg-primary text-on-primary font-bold rounded-lg text-sm"
                  >
                    Send
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Loading / Error / Reconnect banners */}
          {historyLoading && (
            <div className="flex items-center gap-2 text-on-surface-variant text-sm py-2 justify-center">
              <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              Loading conversation history…
            </div>
          )}
          {historyError && (
            <div className="bg-error/10 border border-error/30 rounded-xl px-4 py-2 text-sm text-error flex items-center gap-2">
              ⚠️ {historyError}
            </div>
          )}
          {status === "error" && (
            <div className="bg-error/10 border border-error/30 rounded-xl p-4 text-center animate-in fade-in">
              <div className="flex items-center justify-center gap-2 text-error mb-2">
                <span className="material-symbols-outlined text-lg">
                  cloud_off
                </span>
                <span className="text-sm font-bold">Connection lost</span>
              </div>
              <p className="text-xs text-on-surface-variant mb-3">
                WebSocket closed unexpectedly.
              </p>
              <button
                onClick={retryWorkflow}
                className="px-4 py-2 bg-error text-on-error font-bold rounded-lg text-sm hover:brightness-110 transition-all"
              >
                🔄 Retry
              </button>
            </div>
          )}
          {status === "running" && (
            <div className="flex items-center gap-3 text-on-surface-variant text-sm py-2">
              <span className="material-symbols-outlined text-primary text-sm">psychology</span>
              <div className="flex gap-1">
                <span
                  className="w-2 h-2 rounded-full bg-primary animate-bounce"
                  style={{ animationDelay: "0s" }}
                />
                <span
                  className="w-2 h-2 rounded-full bg-primary animate-bounce"
                  style={{ animationDelay: "0.15s" }}
                />
                <span
                  className="w-2 h-2 rounded-full bg-primary animate-bounce"
                  style={{ animationDelay: "0.3s" }}
                />
              </div>
              Agent is thinking…
            </div>
          )}
          {status === "reconnecting" && (
            <div className="flex items-center gap-3 text-on-surface-variant text-sm py-2 justify-center">
              <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              Reconnecting…
            </div>
          )}

          <div ref={eventsEndRef} />
        </div>

        {/* Inline workflow chat composer */}
        <div className="border-t border-outline-variant/10 px-6 py-3 shrink-0">
          <form onSubmit={handleChat} className="flex gap-2 max-w-4xl mx-auto">
            <input
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              disabled={sending}
              className="flex-1 bg-surface-container-low border border-outline-variant/20 rounded-lg px-3 py-2 text-sm text-on-surface placeholder:text-outline/50 focus:ring-1 focus:ring-primary"
              placeholder="Ask about your workflow output..."
            />
            <button
              type="submit"
              disabled={sending}
              className="w-9 h-9 bg-primary rounded-lg flex items-center justify-center text-on-primary hover:brightness-110 transition-all disabled:opacity-50 shrink-0"
            >
              <span className="material-symbols-outlined text-base">send</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

/* ─── Event Card Component ─── */
function EventCard({ event }) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { projectId } = useParams();
  const ev = event;

  switch (ev.type) {
    case "user_echo":
      return (
        <div className="flex justify-end">
          <div 
            className="bg-surface-container-high rounded-xl rounded-tr-none px-4 py-3 text-sm max-w-[80%] md-content"
            dangerouslySetInnerHTML={{ __html: renderMd(ev.content) }}
          />
        </div>
      );

    case "phase_start":
      return (
        <div className="flex justify-center py-2">
          <div className="px-4 py-1.5 rounded-full text-[11px] font-semibold uppercase tracking-wider bg-surface-container-high border border-outline-variant/20 text-on-surface-variant">
            {ev.phase === "diagram" ? ev.name : `Phase ${ev.phase}: ${ev.name}`}{" "}
            {ev.iteration > 1 ? `(revision ${ev.iteration})` : ""}
          </div>
        </div>
      );

    case "agent_input":
      return (
        <div className="flex items-center gap-2 text-xs text-on-surface-variant py-1">
          <span className="material-symbols-outlined text-primary text-sm">
            psychology
          </span>
          <span>
            Agent <strong className="text-on-surface">{ev.agent}</strong>{" "}
            processing…
          </span>
          <span className="text-outline text-[10px]">{ev.model}</span>
        </div>
      );

    case "tool_call":
      return (
        <div className="flex justify-start">
          <div className="w-full max-w-[92%] border border-outline-variant/20 bg-surface-container-low rounded-xl overflow-hidden">
            <button
              onClick={() => setOpen(!open)}
              className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-surface-container-high/40 transition-colors"
            >
              <span className="material-symbols-outlined text-outline text-base">
                build
              </span>
              <span className="font-medium text-on-surface flex-1">
                Tool call: {ev.tool_name}
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-outline/15 text-on-surface-variant font-medium">
                system
              </span>
              <span className="text-outline text-sm">{open ? "▾" : "▸"}</span>
            </button>
            {open && (
              <div className="px-4 pb-3 text-xs text-on-surface-variant">
                <pre className="bg-surface-container rounded-lg p-3 overflow-x-auto font-[family-name:var(--font-mono)]">
                  {JSON.stringify(ev.tool_kwargs, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      );

    case "rag_result": {
      const toolLabel =
        ev.tool_name === "search_product_specs"
          ? "Product Search"
          : ev.tool_name === "search_across_products"
            ? "Cross-Product Search"
            : "RAG Search";
      return (
        <div className="border border-purple-400/20 bg-purple-500/5 rounded-xl overflow-hidden">
          <button
            onClick={() => setOpen(!open)}
            className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-purple-500/5 transition-colors"
          >
            <span className="material-symbols-outlined text-purple-400 text-lg">
              library_books
            </span>
            <span className="font-medium text-on-surface flex-1">
              {toolLabel}: {ev.total} chunks retrieved
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-400 font-medium">
              retrieval
            </span>
            <span className="text-outline text-sm">{open ? "▾" : "▸"}</span>
          </button>
          {open && (
            <div className="px-4 pb-3 space-y-2 max-h-64 overflow-y-auto custom-scrollbar">
              {(ev.chunks || []).map((c, i) => (
                <div
                  key={i}
                  className="bg-surface-container rounded-lg p-3 border-l-2 border-purple-400/40"
                >
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

    case "tool_result": {
      const isCatalog = ev.tool_name === "list_available_products";
      return (
        <div className="flex justify-start">
          <div
            className={`w-full max-w-[92%] border rounded-xl overflow-hidden ${isCatalog ? "border-cyan-500/20 bg-cyan-500/5" : "border-outline-variant/20 bg-surface-container-low"}`}
          >
            <button
              onClick={() => setOpen(!open)}
              className="w-full flex items-center gap-2 px-4 py-2 text-xs text-left hover:bg-surface-container-high/30 transition-colors"
            >
              <span className="material-symbols-outlined text-outline text-sm">
                {isCatalog ? "inventory_2" : "output"}
              </span>
              <span className="text-on-surface-variant flex-1">
                {isCatalog ? "Product Catalog" : `Tool result: ${ev.tool_name}`}{" "}
                ({ev.output?.length || 0} chars)
              </span>
              <span className="text-outline text-sm">{open ? "▾" : "▸"}</span>
            </button>
            {open && (
              <div className="px-4 pb-3 text-xs text-on-surface-variant">
                <pre className="bg-surface-container rounded-lg p-3 overflow-x-auto font-[family-name:var(--font-mono)] whitespace-pre-wrap">
                  {ev.output}
                </pre>
              </div>
            )}
          </div>
        </div>
      );
    }

    case "config_rag_result":
      return (
        <div className="border border-emerald-500/20 bg-emerald-500/5 rounded-xl overflow-hidden">
          <button
            onClick={() => setOpen(!open)}
            className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-emerald-500/5 transition-colors"
          >
            <span className="material-symbols-outlined text-emerald-400 text-lg">
              terminal
            </span>
            <span className="font-medium text-on-surface flex-1">
              Config Guide Search: {ev.total_chars} chars retrieved
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-medium">
              CLI reference
            </span>
            <span className="text-outline text-sm">{open ? "▾" : "▸"}</span>
          </button>
          {open && (
            <div className="px-4 pb-3 text-xs text-on-surface-variant max-h-64 overflow-y-auto custom-scrollbar">
              <pre className="whitespace-pre-wrap font-[family-name:var(--font-mono)]">
                {ev.output}
              </pre>
            </div>
          )}
        </div>
      );

    case "agent_response":
      if (ev.phase === 4) return null; // Hide React code streaming, we only want the Interactive Topology CTA
      return (
        <div className="flex justify-start">
          <div
            className="max-w-[92%] bg-surface-container-low border border-outline-variant/15 rounded-xl rounded-tl-none px-5 py-4 text-sm md-content"
            dangerouslySetInnerHTML={{ __html: renderMd(ev.content) }}
          />
        </div>
      );

    case "phase_approved":
      return (
        <div className="flex justify-center py-1">
          <span className="text-xs font-medium text-tertiary bg-tertiary/10 px-4 py-1.5 rounded-full border border-tertiary/20">
            Phase {ev.phase || "?"} approved
          </span>
        </div>
      );

    case "user_action":
      return (
        <div className="flex justify-end">
          <div className="bg-surface-container-high rounded-xl rounded-tr-none px-4 py-2.5 text-sm max-w-[80%]">
            {ev.content}
          </div>
        </div>
      );

    case "workflow_complete":
      return (
        <>
          <div className="flex justify-center py-1">
            <span className="text-xs font-semibold text-tertiary bg-tertiary/12 px-4 py-1.5 rounded-full border border-tertiary/20">
              Workflow complete
            </span>
          </div>
          <WorkflowCompleteCard />
        </>
      );

    case "error":
      return (
        <div className="bg-error/10 border border-error/30 rounded-xl px-4 py-3 text-sm text-error">
          ❌ {ev.message}
        </div>
      );

    case "diagram_ready":
      return (
        <div className="border border-tertiary/30 bg-tertiary/5 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-tertiary/15">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-tertiary text-lg">
                schema
              </span>
              <span className="text-sm font-bold text-on-surface">
                Network Topology Diagram
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-tertiary/20 text-tertiary font-medium">
                interactive
              </span>
            </div>
          </div>
          <div className="p-5 bg-surface-container-low rounded-b-xl flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-tertiary/15 flex items-center justify-center text-tertiary shrink-0">
                <span className="material-symbols-outlined text-lg">schema</span>
              </div>
              <div>
                <h3 className="text-sm font-bold text-on-surface">
                  Interactive Topology Ready
                </h3>
                <p className="text-xs text-on-surface-variant mt-0.5">
                  View your network topology diagram.
                </p>
              </div>
            </div>
            <button
              onClick={() =>
                navigate(`/project/${projectId}/interactive-topology`)
              }
              className="shrink-0 px-5 py-2.5 bg-tertiary text-on-tertiary font-bold rounded-lg hover:brightness-110 transition-all flex items-center gap-2 text-sm shadow-sm"
            >
              View Topology
              <span className="material-symbols-outlined text-base">
                open_in_new
              </span>
            </button>
          </div>
        </div>
      );

    case "diagram_error":
      return (
        <div className="border border-tertiary/30 bg-tertiary/5 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-tertiary/15">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-tertiary text-lg">
                schema
              </span>
              <span className="text-sm font-bold text-on-surface">
                Network Topology Diagram
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-tertiary/20 text-tertiary font-medium">
                interactive
              </span>
            </div>
          </div>
          <div className="p-5 bg-surface-container-low rounded-b-xl flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-tertiary/15 flex items-center justify-center text-tertiary shrink-0">
                <span className="material-symbols-outlined text-lg">schema</span>
              </div>
              <div>
                <h3 className="text-sm font-bold text-on-surface">
                  Interactive Topology Ready
                </h3>
                <p className="text-xs text-on-surface-variant mt-0.5">
                  View your network topology diagram.
                </p>
              </div>
            </div>
            <button
              onClick={() =>
                navigate(`/project/${projectId}/interactive-topology`)
              }
              className="shrink-0 px-5 py-2.5 bg-tertiary text-on-tertiary font-bold rounded-lg hover:brightness-110 transition-all flex items-center gap-2 text-sm shadow-sm"
            >
              View Topology
              <span className="material-symbols-outlined text-base">
                open_in_new
              </span>
            </button>
          </div>
        </div>
      );

    default:
      return null;
  }
}

/* ─── Workflow Complete Card ─── */
function WorkflowCompleteCard() {
  const navigate = useNavigate();
  const { projectId } = useParams();

  return (
    <div className="mt-2 bg-tertiary/8 border border-tertiary/30 rounded-xl overflow-hidden animate-in fade-in">
      {/* Completion badge */}
      <div className="flex justify-center pt-5 pb-3">
        <div className="px-5 py-1.5 rounded-full text-xs font-bold bg-tertiary/15 border border-tertiary/30 text-tertiary flex items-center gap-2">
          <span className="material-symbols-outlined text-sm">
            check_circle
          </span>
          Workflow Complete
        </div>
      </div>
    </div>
  );
}
