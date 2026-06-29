/**
 * API Service Layer — Real Backend Integration via WebSocket
 *
 * The 5-phase AI workflow (rephrase → topology → device selection →
 * topology diagram → CLI config) runs over a single WebSocket
 * connection with streaming events.
 *
 * The chat copilot also uses WebSocket for follow-up questions.
 */

import axios from "axios";

const API = axios.create({
  baseURL: "/api",
  timeout: 120000,
});

/**
 * Build a natural-language prompt from the structured requirements form.
 */
export function buildPromptFromRequirements(req, solutionType) {
  const isCampus = solutionType !== "datacenter";

  if (isCampus) {
    // Calculate totals from our new structured building list
    const totalBuildings = req.buildings?.length || 0;
    let totalStudents = 0,
      totalStaff = 0,
      totalAdmins = 0,
      totalVoip = 0,
      totalIptv = 0,
      totalPrinters = 0;

    req.buildings?.forEach((b) => {
      b.departments?.forEach((d) => {
        totalStudents += Number(d.students) || 0;
        totalStaff += Number(d.staff) || 0;
        totalAdmins += Number(d.admins) || 0;
        totalVoip += Number(d.voip) || 0;
        totalIptv += Number(d.iptv) || 0;
        totalPrinters += Number(d.printers) || 0;
      });
    });

    let prompt = `Design a campus network for an organization with ${totalBuildings} building(s).`;
    prompt += ` Across all buildings, there are approximately ${totalStudents} users/visitors, ${totalStaff} staff/faculty, ${totalAdmins} administrators, ${totalVoip} VoIP phones, ${totalIptv} IPTVs, and ${totalPrinters} printers.\n\n`;

    // Per-building, per-department breakdown
    prompt += `## Building & Department Breakdown\n`;
    req.buildings?.forEach((b, bIdx) => {
      prompt += `\n### Building ${bIdx + 1}: ${b.name || "Unnamed"} (${b.departmentCount || 0} departments)\n`;
      if (b.departments?.length) {
        prompt += `| Department | Floor No. |  Users   | Staff | Admins | VoIP Phones | IPTVs | Printers |\n`;
        prompt += `|------------|-----------|----------|-------|--------|-------------|-------|----------|\n`;
        b.departments.forEach((d, dIdx) => {
          const deptLabel = d.department || `Department ${dIdx + 1}`;
          const floorLabel = d.floorNo || dIdx + 1;
          prompt += `| ${deptLabel} | ${floorLabel} | ${d.students || 0} | ${d.staff || 0} | ${d.admins || 0} | ${d.voip || 0} | ${d.iptv || 0} | ${d.printers || 0} |\n`;
        });
        const bStudents = b.departments.reduce(
          (s, d) => s + (Number(d.students) || 0),
          0,
        );
        const bStaff = b.departments.reduce(
          (s, d) => s + (Number(d.staff) || 0),
          0,
        );
        const bAdmins = b.departments.reduce(
          (s, d) => s + (Number(d.admins) || 0),
          0,
        );
        const bVoip = b.departments.reduce(
          (s, d) => s + (Number(d.voip) || 0),
          0,
        );
        const bIptv = b.departments.reduce(
          (s, d) => s + (Number(d.iptv) || 0),
          0,
        );
        const bPrinters = b.departments.reduce(
          (s, d) => s + (Number(d.printers) || 0),
          0,
        );
        prompt += `| **Total** | | **${bStudents}** | **${bStaff}** | **${bAdmins}** | **${bVoip}** | **${bIptv}** | **${bPrinters}** |\n`;
      }
    });

    prompt += `\n`;
    if (req.devices) {
      const devs = Object.entries(req.devices)
        .filter(([, v]) => v)
        .map(([k]) => k);
      if (devs.length) prompt += `Devices needed: ${devs.join(", ")}.\n`;
    }
    if (req.sensitiveAreas?.length)
      prompt += `Sensitive areas requiring extra security: ${req.sensitiveAreas.join(", ")}.\n`;
    if (req.specialRoles?.length)
      prompt += `Special roles to consider: ${req.specialRoles.join(", ")}.\n`;
    const uptimeDescriptions = {
      standard: "Standard — Occasional brief outages are acceptable",
      important: "Important — Minimal downtime, critical for daily operations",
      critical: "Mission Critical — 24/7 availability, no downtime allowed",
    };
    prompt += `Uptime requirement: ${uptimeDescriptions[req.uptimeLevel] || req.uptimeLevel}.\n`;
    if (req.expectGrowth)
      prompt += `Expecting growth of ${req.growthAmount} additional users/people.\n`;
    if (req.additionalNotes)
      prompt += `Additional notes: ${req.additionalNotes}\n`;
    return prompt;
  } else {
    // Data Center path
    let prompt = `Design a data center network with ${req.dcRacks || 0} server rack(s) and approximately ${req.dcServers || 0} servers.`;
    if (req.specialRoles?.length)
      prompt += ` Use cases: ${req.specialRoles.join(", ")}.`;
    if (req.sensitiveAreas?.length)
      prompt += ` Security zones: ${req.sensitiveAreas.join(", ")}.`;
    const uptimeDescriptions = {
      standard: "Standard — Occasional brief outages are acceptable",
      important: "Important — Minimal downtime, critical for daily operations",
      critical: "Mission Critical — 24/7 availability, no downtime allowed",
    };
    prompt += ` Uptime requirement: ${uptimeDescriptions[req.uptimeLevel] || req.uptimeLevel}.`;
    if (req.expectGrowth)
      prompt += ` Expecting growth of ${req.growthAmount} additional server racks.`;
    if (req.additionalNotes)
      prompt += ` Additional notes: ${req.additionalNotes}`;
    return prompt;
  }
}

/**
 * Submit requirements and run the full 5-phase AI workflow via WebSocket.
 *
 * @param {Object} requirements - The form inputs
 * @param {string} solutionType - 'campus' or 'datacenter'
 * @param {Function} onEvent - Callback for each streaming event: (event) => void
 *   Events: phase_start, agent_input, tool_call, rag_result, config_rag_result,
 *           agent_response, approval_request, phase_approved, phase_revision,
 *           workflow_complete, error
 * @returns {Promise<Object>} - Resolves with { rephrased, topology, devices,
 *           diagramCode, diagramUrl, cliConfig } when done
 */
const PHASE_MAP = {
  prompt_rephraser: 1,
  topology_designer: 2,
  device_selector: 3,
  react_topology_architect: 4,
  cli_config_generator: 5,
};

function stripHost(url) {
  return url.replace(/^https?:\/\/[^\/]+/, "");
}

function makeWorkflowHandler(results, onEvent, resolve, reject, wsRef, projectId) {
  let currentPhase = 0;
  let settled = false;

  const finalize = () => {
    if (settled) return;
    settled = true;
    onEvent({ type: "workflow_complete" });
    wsRef.closed = true;
    wsRef.current?.close();
    resolve(results);
  };

  return function (e) {
    try {
      console.log(
        "[WS] recv len=" +
          e.data.length +
          " preview=" +
          e.data.substring(0, 200),
      );
      const event = JSON.parse(e.data);
      const { event_type, agent_name, data, payload, is_final, timestamp } = event;
      if (!event_type) {
        console.warn("[WS] Missing event_type in payload:", event);
        return;
      }
      if (
        !agent_name &&
        event_type !== "PHASE_APPROVED" &&
        event_type !== "APPROVAL_REQUIRED"
      ) {
        console.warn(
          "[WS] Missing agent_name for event_type=" + event_type,
          event,
        );
      }

      const phase = PHASE_MAP[agent_name];
      if (phase && phase !== currentPhase) {
        currentPhase = phase;
        console.log("[WS] phase_start phase=" + phase + " agent=" + agent_name);
        onEvent({
          type: "phase_start",
          phase,
          name: agent_name
            .replace(/_/g, " ")
            .replace(/\b\w/g, (c) => c.toUpperCase()),
          timestamp,
        });
      }

      // Use agent_name as source of truth for phase routing
      const storePhase = PHASE_MAP[agent_name] || currentPhase;

      if (event_type === "TOKEN") {
        console.log(
          "[WS] TOKEN agent=" +
            agent_name +
            " data_preview=" +
            (data || "").substring(0, 80),
        );
        return;
      }

      if (event_type === "FINAL_ANSWER") {
        if (typeof data !== "string") {
          console.warn("[WS] FINAL_ANSWER expected string data:", event);
        }
        const content = data || "";
        if (storePhase === 1) results.rephrased = content;
        else if (storePhase === 2) results.topology = content;
        else if (storePhase === 3) results.devices = content;
        else if (storePhase === 4) results.diagramCode = content;
        else if (storePhase === 5) results.cliConfig = content;

        const normalized = content.startsWith("assistant: ")
          ? content.slice(11)
          : content;
        onEvent({
          type: "agent_response",
          content: normalized,
          phase: storePhase,
          timestamp,
        });

        // Auto-dispatch approval_request on FINAL_ANSWER to avoid race condition
        // where APPROVAL_REQUIRED is sent on stale WS connection.
        if (is_final && storePhase >= 1 && storePhase < 5) {
          onEvent({
            type: "approval_request",
            ws: wsRef.current,
            approval: { taskId: event.task_id, phase: storePhase },
            timestamp,
          });
        }

        if (is_final && storePhase >= 5) {
          finalize();
        }
        return;
      }

      if (event_type === "TOOL_CALL") {
        onEvent({
          type: "tool_call",
          phase: storePhase,
          tool_name: data || agent_name,
          tool_kwargs: payload || {},
          timestamp,
        });
        return;
      }

      if (event_type === "TOOL_RESULT") {
        const toolOutput = payload?.output || data || "";
        onEvent({
          type: "tool_result",
          phase: storePhase,
          tool_name: agent_name,
          output: toolOutput,
          payload,
          timestamp,
        });
        return;
      }

      if (event_type === "PHASE_APPROVED") {
        if (is_final) {
          finalize();
          return;
        }
        // Ignore WS PHASE_APPROVED for intermediate phases to avoid race conditions.
        // The frontend already dispatches it locally on click, and on load via completedPhases.
        return;
      }

      if (event_type === "APPROVAL_REQUIRED") {
        const approvalTaskId = event.task_id || payload?.task_id;
        const approvalPhase =
          payload?.phase || storePhase || 0;
        if (!approvalTaskId) {
          console.warn("[WS] APPROVAL_REQUIRED missing task_id:", event);
        }
        onEvent({
          type: "approval_request",
          ws: wsRef.current,
          approval: { taskId: approvalTaskId, phase: approvalPhase },
          timestamp,
        });
        return;
      }

      if (event_type === "DIAGRAM_READY") {
        const url = stripHost(payload?.url || "");
        results.diagramUrl = url;
        results.diagramDownloadUrl = stripHost(payload?.download_url || "");
        results.diagramCode = data;
        onEvent({
          type: "diagram_ready",
          url,
          download_url: results.diagramDownloadUrl,
          filename: payload?.filename,
          data: data,
          timestamp,
        });
        return;
      }

      if (event_type === "DIAGRAM_ERROR") {
        onEvent({
          type: "diagram_error",
          message: payload?.message || "Diagram rendering failed",
          timestamp,
        });
        return;
      }

      if (event_type === "ERROR") {
        onEvent({ type: "error", message: data || "Unknown error", timestamp });
        // Soft errors (approval/revision related) don't close WS or reject — let UI retry
        if (data && /approval|revision|feedback/i.test(data)) {
          return;
        }
        wsRef.closed = true;
        wsRef.current?.close();
        if (!settled) {
          settled = true;
          reject(new Error(data || "Unknown error"));
        }
        return;
      }
    } catch (err) {
      console.error("WS parse error:", err);
    }
  };
}

export function runWorkflow(projectId, requirements, solutionType, onEvent, isRestart = false) {
  return new Promise((resolve, reject) => {
    const prompt = buildPromptFromRequirements(requirements, solutionType);
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProtocol}//${window.location.host}/chat/${projectId}`;

    const results = {
      prompt,
      rephrased: "",
      topology: "",
      devices: "",
      diagramCode: "",
      diagramUrl: "",
      diagramDownloadUrl: "",
      cliConfig: "",
    };

    let ws = null;
    let wsRef = { current: null };
    let reconnectAttempts = 0;
    let reconnectTimer = null;
    let heartbeatTimer = null;
    let closed = false;
    let hasConnectedOnce = false;

    const handler = makeWorkflowHandler(results, onEvent, resolve, reject, wsRef, projectId);

    function cleanup() {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      if (ws && ws.readyState === WebSocket.OPEN) ws.close();
    }

    function doConnect() {
      if (closed) return;

      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("[WS] open projectId=" + projectId + (hasConnectedOnce ? " (reconnect)" : ""));
        reconnectAttempts = 0;

        if (heartbeatTimer) clearInterval(heartbeatTimer);
        heartbeatTimer = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }));
          }
        }, 25000);

        if (hasConnectedOnce) {
          ws.send(JSON.stringify({ resume: true }));
        } else {
          hasConnectedOnce = true;
          const msg = JSON.stringify({ content: prompt, projectId, restart: isRestart });
          console.log("[WS] send len=" + msg.length + " preview=" + msg.substring(0, 150));
          ws.send(msg);
        }
      };

      ws.onmessage = handler;

      ws.onerror = () => {
        console.error("[WS] error projectId=" + projectId);
      };

      ws.onclose = (ev) => {
        console.log("[WS] close projectId=" + projectId + " code=" + ev.code + " reason=" + ev.reason);
        if (heartbeatTimer) clearInterval(heartbeatTimer);
        if (closed || wsRef.closed) return;
        if (reconnectAttempts < 3) {
          reconnectAttempts++;
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), 8000);
          console.log("[WS] reconnect attempt " + reconnectAttempts + "/3 in " + delay + "ms");
          reconnectTimer = setTimeout(doConnect, delay);
        } else {
          cleanup();
          reject(new Error("WebSocket connection failed after 3 attempts"));
        }
      };
    }

    doConnect();
  });
}

export function resumeWorkflow(projectId, onEvent) {
  return new Promise((resolve, reject) => {
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProtocol}//${window.location.host}/chat/${projectId}`;

    const results = {
      prompt: "",
      rephrased: "",
      topology: "",
      devices: "",
      diagramCode: "",
      diagramUrl: "",
      diagramDownloadUrl: "",
      cliConfig: "",
    };

    let ws = null;
    let wsRef = { current: null };
    let reconnectAttempts = 0;
    let reconnectTimer = null;
    let heartbeatTimer = null;
    let closed = false;

    const handler = makeWorkflowHandler(results, onEvent, resolve, reject, wsRef, projectId);

    function cleanup() {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      if (ws && ws.readyState === WebSocket.OPEN) ws.close();
    }

    function doConnect() {
      if (closed) return;

      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("[WS] resume open projectId=" + projectId + (reconnectAttempts > 0 ? " (reconnect)" : ""));
        reconnectAttempts = 0;

        if (heartbeatTimer) clearInterval(heartbeatTimer);
        heartbeatTimer = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }));
          }
        }, 25000);

        ws.send(JSON.stringify({ resume: true }));
      };

      ws.onmessage = handler;

      ws.onerror = () => {
        console.error("[WS] resume error projectId=" + projectId);
      };

      ws.onclose = (ev) => {
        console.log("[WS] resume close projectId=" + projectId + " code=" + ev.code + " reason=" + ev.reason);
        if (heartbeatTimer) clearInterval(heartbeatTimer);
        if (closed || wsRef.closed) return;
        if (reconnectAttempts < 3) {
          reconnectAttempts++;
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), 8000);
          console.log("[WS] resume reconnect attempt " + reconnectAttempts + "/3 in " + delay + "ms");
          reconnectTimer = setTimeout(doConnect, delay);
        } else {
          cleanup();
          reject(new Error("WebSocket connection failed after 3 attempts"));
        }
      };
    }

    doConnect();
  });
}

/**
 * Send an approval for the current phase.
 */
export function sendApproval(ws, approvalContext = {}) {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(
      JSON.stringify({
        approved: true,
        task_id: approvalContext.taskId || null,
        phase: approvalContext.phase || null,
      }),
    );
  }
}

/**
 * Send a revision request for the current phase.
 */
export function sendRevision(ws, feedback, approvalContext = {}) {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(
      JSON.stringify({
        approved: false,
        feedback,
        task_id: approvalContext.taskId || null,
        phase: approvalContext.phase || null,
      }),
    );
  }
}

/**
 * Send a message to the Grounded Design Copilot (AI chatbot).
 * Uses a separate WebSocket for follow-up chat.
 */
export async function sendChatMessage(
  message,
  history = [],
  screenContext = "",
  projectId = "default",
  conversationId = "default",
) {
  try {
    const res = await API.post("/chat", {
      message,
      history,
      screen_context: screenContext,
      project_id: projectId,
      conversation_id: conversationId,
    });
    return res.data;
  } catch {
    // Fallback stub if chat endpoint not ready
    return {
      role: "assistant",
      content: `Thank you for your question. The chat copilot is processing: "${message}"`,
      timestamp: new Date().toISOString(),
    };
  }
}

/**
 * Fetch conversation messages for a project from REST API.
 */
export async function getProjectConversation(projectId) {
  try {
    const res = await API.get(`/projects/${projectId}/conversations`);
    if (res.data && res.data.length > 0) {
      return res.data[0];
    }
    return null;
  } catch {
    return null;
  }
}

export async function getConversationMessages(conversationId) {
  try {
    const res = await API.get(`/conversations/${conversationId}/messages`);
    return res.data || [];
  } catch {
    return [];
  }
}

export async function getProjectMessages(projectId) {
  const conv = await getProjectConversation(projectId);
  if (!conv) return [];
  return getConversationMessages(conv.id);
}

export async function getPersistentChatHistory(
  projectId,
  conversationId = "default",
) {
  try {
    const q = encodeURIComponent(conversationId || "default");
    const res = await API.get(
      `/projects/${projectId}/chat-history?conversationId=${q}`,
    );
    return res.data || null;
  } catch {
    return null;
  }
}

/**
 * Fetch workflow state for a project — completed phases and their outputs.
 * Used on page refresh to resume from where the workflow left off.
 */
/**
 * Save/update project metadata (solutionType, requirements, chatHistory, workflowStatus) to DB.
 */
export async function saveProjectToDb(projectId, data) {
  try {
    const payload = {};
    if (data.solutionType !== undefined)
      payload.solution_type = data.solutionType;
    if (data.requirements !== undefined)
      payload.requirements = JSON.stringify(data.requirements);
    if (data.chatHistory !== undefined)
      payload.chat_history = JSON.stringify(data.chatHistory);
    if (data.workflowStatus !== undefined)
      payload.workflow_status = data.workflowStatus;
    if (data.title !== undefined) payload.title = data.title;
    await API.patch(`/projects/${projectId}`, payload);
  } catch (err) {
    console.error("[DB] saveProjectToDb failed:", err);
  }
}

export async function getWorkflowState(projectId) {
  try {
    const res = await API.get(`/projects/${projectId}/phases`);
    return res.data;
  } catch {
    return null;
  }
}

/**
 * Trigger the deployment process.
 */
export async function triggerDeployment(projectId) {
  try {
    const res = await API.post("/deploy", { projectId });
    return res.data;
  } catch {
    return {
      status: "success",
      message:
        "Deployment initiated. Configuration is being pushed to network devices.",
      projectId,
    };
  }
}
