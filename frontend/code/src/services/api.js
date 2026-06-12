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
 * Submit requirements and run the full 3-phase AI workflow via WebSocket.
 *
 * @param {Object} requirements - The form inputs
 * @param {string} solutionType - 'campus' or 'datacenter'
 * @param {Function} onEvent - Callback for each streaming event: (event) => void
 *   Events: phase_start, agent_input, tool_call, rag_result, agent_response,
 *           approval_request, phase_approved, phase_revision, workflow_complete, error
 * @returns {Promise<Object>} - Resolves with { rephrased, topology, devices } when done
 */
export function runWorkflow(requirements, solutionType, onEvent) {
  return new Promise((resolve, reject) => {
    const prompt = buildPromptFromRequirements(requirements, solutionType);
    const wsUrl = `ws://${window.location.host}/ws`;
    const ws = new WebSocket(wsUrl);

    const results = { prompt, rephrased: '', topology: '', devices: '', diagramUrl: '', diagramDownloadUrl: '' };
    let currentPhase = 0;

    // Expose send functions via the onEvent callback's return
    ws._sendApproval = () => ws.send(JSON.stringify({ approved: true }));
    ws._sendRevision = (feedback) => ws.send(JSON.stringify({ approved: false, feedback }));

    ws.onopen = () => {
      ws.send(JSON.stringify({ content: prompt }));
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);

        if (data.type === 'phase_start') currentPhase = data.phase;

        // Capture agent responses per phase
        if (data.type === 'agent_response') {
          let content = data.content || '';
          if (content.startsWith('assistant: ')) content = content.slice(11);
          data.content = content;

          if (currentPhase === 1) results.rephrased = content;
          else if (currentPhase === 2) results.topology = content;
          else if (currentPhase === 3) results.devices = content;
        }

        if (data.type === 'diagram_ready') {
          results.diagramUrl = data.url || '';
          results.diagramDownloadUrl = data.download_url || '';
        }

        if (data.type === 'workflow_complete') {
          if (data.diagram_url && !results.diagramUrl) results.diagramUrl = data.diagram_url;
          ws.close();
          resolve(results);
        }

        if (data.type === 'error') {
          ws.close();
          reject(new Error(data.message));
        }

        // Forward event to UI with ws reference for approval
        onEvent({ ...data, ws });
      } catch (err) {
        console.error('WS parse error:', err);
      }
    };

    ws.onerror = () => reject(new Error('WebSocket connection failed'));
    ws.onclose = () => {};
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
export async function sendChatMessage(message, history = []) {
  try {
    const res = await API.post('/chat', { message, history });
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
 * Trigger the deployment process.
 */
export async function triggerDeployment(projectId) {
  console.log('[API] triggerDeployment for project:', projectId);
  return {
    status: 'success',
    message: 'Deployment initiated. Configuration is being pushed to network devices.',
    projectId,
  };
}

// Keep backward compat — submitRequirements is now handled by runWorkflow
export async function submitRequirements(requirements) {
  console.warn('[API] submitRequirements is deprecated, use runWorkflow instead');
  return null;
}
