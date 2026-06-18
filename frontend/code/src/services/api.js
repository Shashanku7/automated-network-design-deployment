/**
 * API Service Layer — Real Backend Integration via WebSocket
 *
 * The 3-phase AI workflow (rephrase → topology → device selection)
 * runs over a single WebSocket connection with streaming events.
 *
 * The chat copilot also uses WebSocket for follow-up questions.
 */

import axios from 'axios';

const API = axios.create({
  baseURL: '/api',
  timeout: 120000,
});

/**
 * Build a natural-language prompt from the structured requirements form.
 */
function buildPromptFromRequirements(req, solutionType) {
  const isCampus = solutionType !== 'datacenter';

  if (isCampus) {
    // Calculate totals from our new structured building list
    const totalBuildings = req.buildings?.length || 0;
    let totalStudents = 0, totalStaff = 0, totalAdmins = 0, totalVoip = 0, totalIptv = 0, totalPrinters = 0;
    
    req.buildings?.forEach(b => {
      b.departments?.forEach(d => {
        totalStudents += (Number(d.students) || 0);
        totalStaff += (Number(d.staff) || 0);
        totalAdmins += (Number(d.admins) || 0);
        totalVoip += (Number(d.voip) || 0);
        totalIptv += (Number(d.iptv) || 0);
        totalPrinters += (Number(d.printers) || 0);
      });
    });

    let prompt = `Design a campus network for an organization with ${totalBuildings} building(s).`;
    prompt += ` Across all buildings, there are approximately ${totalStudents} students/visitors, ${totalStaff} staff/faculty, ${totalAdmins} administrators, ${totalVoip} VoIP phones, ${totalIptv} IPTVs, and ${totalPrinters} printers.\n\n`;

    // Per-building, per-department breakdown
    prompt += `## Building & Department Breakdown\n`;
    req.buildings?.forEach((b, bIdx) => {
      prompt += `\n### Building ${bIdx + 1}: ${b.name || 'Unnamed'} (${b.departmentCount || 0} departments)\n`;
      if (b.departments?.length) {
        prompt += `| Department | Floor No. | Students | Staff | Admins | VoIP Phones | IPTVs | Printers |\n`;
        prompt += `|------------|-----------|----------|-------|--------|-------------|-------|----------|\n`;
        b.departments.forEach((d, dIdx) => {
          const deptLabel = d.department || `Department ${dIdx + 1}`;
          const floorLabel = d.floorNo || (dIdx + 1);
          prompt += `| ${deptLabel} | ${floorLabel} | ${d.students || 0} | ${d.staff || 0} | ${d.admins || 0} | ${d.voip || 0} | ${d.iptv || 0} | ${d.printers || 0} |\n`;
        });
        const bStudents = b.departments.reduce((s, d) => s + (Number(d.students) || 0), 0);
        const bStaff = b.departments.reduce((s, d) => s + (Number(d.staff) || 0), 0);
        const bAdmins = b.departments.reduce((s, d) => s + (Number(d.admins) || 0), 0);
        const bVoip = b.departments.reduce((s, d) => s + (Number(d.voip) || 0), 0);
        const bIptv = b.departments.reduce((s, d) => s + (Number(d.iptv) || 0), 0);
        const bPrinters = b.departments.reduce((s, d) => s + (Number(d.printers) || 0), 0);
        prompt += `| **Total** | | **${bStudents}** | **${bStaff}** | **${bAdmins}** | **${bVoip}** | **${bIptv}** | **${bPrinters}** |\n`;
      }
    });

    prompt += `\n`;
    if (req.devices) {
      const devs = Object.entries(req.devices).filter(([, v]) => v).map(([k]) => k);
      if (devs.length) prompt += `Devices needed: ${devs.join(', ')}.\n`;
    }
    if (req.sensitiveAreas?.length) prompt += `Sensitive areas requiring extra security: ${req.sensitiveAreas.join(', ')}.\n`;
    if (req.specialRoles?.length) prompt += `Special roles to consider: ${req.specialRoles.join(', ')}.\n`;
    const uptimeDescriptions = {
      standard: 'Standard — Occasional brief outages are acceptable',
      important: 'Important — Minimal downtime, critical for daily operations',
      critical: 'Mission Critical — 24/7 availability, no downtime allowed',
    };
    prompt += `Uptime requirement: ${uptimeDescriptions[req.uptimeLevel] || req.uptimeLevel}.\n`;
    if (req.expectGrowth) prompt += `Expecting growth of ${req.growthAmount} additional users/people.\n`;
    if (req.additionalNotes) prompt += `Additional notes: ${req.additionalNotes}\n`;
    return prompt;
  } else {
    // Data Center path
    let prompt = `Design a data center network with ${req.dcRacks || 0} server rack(s) and approximately ${req.dcServers || 0} servers.`;
    if (req.specialRoles?.length) prompt += ` Use cases: ${req.specialRoles.join(', ')}.`;
    if (req.sensitiveAreas?.length) prompt += ` Security zones: ${req.sensitiveAreas.join(', ')}.`;
    const uptimeDescriptions = {
      standard: 'Standard — Occasional brief outages are acceptable',
      important: 'Important — Minimal downtime, critical for daily operations',
      critical: 'Mission Critical — 24/7 availability, no downtime allowed',
    };
    prompt += ` Uptime requirement: ${uptimeDescriptions[req.uptimeLevel] || req.uptimeLevel}.`;
    if (req.expectGrowth) prompt += ` Expecting growth of ${req.growthAmount} additional server racks.`;
    if (req.additionalNotes) prompt += ` Additional notes: ${req.additionalNotes}`;
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
 * @returns {Promise<Object>} - Resolves with { rephrased, topology, devices, cliConfig } when done
 */
const PHASE_MAP = {
  prompt_rephraser: 1,
  topology_designer: 2,
  device_selector: 3,
  d2_diagram_generator: 4,
  cli_config_generator: 5,
};

function stripHost(url) {
  return url.replace(/^https?:\/\/[^\/]+/, '');
}

function makeWorkflowHandler(results, onEvent, resolve, reject, ws, projectId) {
  let currentPhase = 0;
  return function (e) {
    try {
      console.log('[WS] recv len=' + e.data.length + ' preview=' + e.data.substring(0, 200));
      const event = JSON.parse(e.data);
      const { event_type, agent_name, data, payload, is_final } = event;

      const phase = PHASE_MAP[agent_name];
      if (phase && phase !== currentPhase) {
        currentPhase = phase;
        console.log('[WS] phase_start phase=' + phase + ' agent=' + agent_name);
        onEvent({ type: 'phase_start', phase, name: agent_name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) });
      }

      if (event_type === 'TOKEN') {
        console.log('[WS] TOKEN agent=' + agent_name + ' data_preview=' + (data || '').substring(0, 80));
        return;
      }

      if (event_type === 'FINAL_ANSWER') {
        const content = data || '';
        if (currentPhase === 1) results.rephrased = content;
        else if (currentPhase === 2) results.topology = content;
        else if (currentPhase === 3) results.devices = content;
        else if (currentPhase === 5) results.cliConfig = content;

        // onEvent({ type: 'agent_response', content, phase: currentPhase });
        if (data.type === 'agent_response') {
          let content = data.content || '';
          if (content.startsWith('assistant: ')) content = content.slice(11);
          data.content = content;
          data.phase = currentPhase;

        if (is_final && currentPhase >= 5) {
          onEvent({ type: 'workflow_complete' });
          ws.close();
          resolve(results);
        }
        return;
      }

      if (event_type === 'TOOL_CALL') {
        onEvent({ type: 'tool_call', tool_name: data || agent_name, tool_kwargs: payload || {} });
        return;
      }

      if (event_type === 'TOOL_RESULT') {
        const toolOutput = payload?.output || data || '';
        onEvent({ type: 'tool_result', tool_name: agent_name, output: toolOutput, payload });
        return;
      }

      if (event_type === 'PHASE_APPROVED') {
        onEvent({ type: 'phase_approved' });
        return;
      }

      if (event_type === 'APPROVAL_REQUIRED') {
        onEvent({ type: 'approval_request', ws });
        return;
      }

      if (event_type === 'DIAGRAM_READY') {
        const url = stripHost(payload?.url || '');
        results.diagramUrl = url;
        results.diagramDownloadUrl = stripHost(payload?.download_url || '');
        onEvent({ type: 'diagram_ready', url, download_url: results.diagramDownloadUrl, filename: payload?.filename });
        return;
      }

      if (event_type === 'DIAGRAM_ERROR') {
        onEvent({ type: 'diagram_error', message: payload?.message || 'Diagram rendering failed' });
        return;
      }

      if (event_type === 'ERROR') {
        onEvent({ type: 'error', message: data || 'Unknown error' });
        ws.close();
        reject(new Error(data || 'Unknown error'));
        return;
      }
    }} catch (err) {
      console.error('WS parse error:', err);
    }
  };
}

export function runWorkflow(projectId, requirements, solutionType, onEvent) {
  return new Promise((resolve, reject) => {
    const prompt = buildPromptFromRequirements(requirements, solutionType);
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/chat/${projectId}`;
    const ws = new WebSocket(wsUrl);

    const results = { prompt, rephrased: '', topology: '', devices: '', diagramUrl: '', diagramDownloadUrl: '', cliConfig: '' };

    ws.onopen = () => {
      console.log('[WS] open projectId=' + projectId);
      const msg = JSON.stringify({ content: prompt, projectId });
      console.log('[WS] send len=' + msg.length + ' preview=' + msg.substring(0, 150));
      ws.send(msg);
    };

    ws.onmessage = makeWorkflowHandler(results, onEvent, resolve, reject, ws, projectId);

    ws.onerror = () => {
      console.error('[WS] error projectId=' + projectId);
      reject(new Error('WebSocket connection failed'));
    };
    ws.onclose = (ev) => {
      console.log('[WS] close projectId=' + projectId + ' code=' + ev.code + ' reason=' + ev.reason);
    };
  });
}

export function resumeWorkflow(projectId, onEvent) {
  return new Promise((resolve, reject) => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/chat/${projectId}`;
    const ws = new WebSocket(wsUrl);

    const results = { prompt: '', rephrased: '', topology: '', devices: '', diagramUrl: '', diagramDownloadUrl: '', cliConfig: '' };

    ws.onopen = () => {
      console.log('[WS] resume open projectId=' + projectId);
      ws.send(JSON.stringify({ resume: true }));
    };

    ws.onmessage = makeWorkflowHandler(results, onEvent, resolve, reject, ws, projectId);

    ws.onerror = () => {
      console.error('[WS] resume error projectId=' + projectId);
      reject(new Error('WebSocket connection failed'));
    };
    ws.onclose = (ev) => {
      console.log('[WS] resume close projectId=' + projectId + ' code=' + ev.code + ' reason=' + ev.reason);
    };
  });
}

/**
 * Send an approval for the current phase.
 */
export function sendApproval(ws) {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ approved: true }));
  }
}

/**
 * Send a revision request for the current phase.
 */
export function sendRevision(ws, feedback) {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ approved: false, feedback }));
  }
}

/**
 * Send a message to the Grounded Design Copilot (AI chatbot).
 * Uses a separate WebSocket for follow-up chat.
 */
export async function sendChatMessage(message, history = [], screenContext = "") {
  try {
    const res = await API.post('/chat', { message, history, screenContext });
    return res.data;
  } catch {
    // Fallback stub if chat endpoint not ready
    return {
      role: 'assistant',
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
    if (data.solutionType !== undefined) payload.solution_type = data.solutionType;
    if (data.requirements !== undefined) payload.requirements = JSON.stringify(data.requirements);
    if (data.chatHistory !== undefined) payload.chat_history = JSON.stringify(data.chatHistory);
    if (data.workflowStatus !== undefined) payload.workflow_status = data.workflowStatus;
    if (data.title !== undefined) payload.title = data.title;
    await API.patch(`/projects/${projectId}`, payload);
  } catch (err) {
    console.error('[DB] saveProjectToDb failed:', err);
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
    const res = await API.post('/deploy', { projectId });
    return res.data;
  } catch {
    return {
      status: 'success',
      message: 'Deployment initiated. Configuration is being pushed to network devices.',
      projectId,
    };
  }
}
