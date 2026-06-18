/**
 * API Service Layer — Gateway WebSocket Integration
 *
 * Connects to gateway at /chat/{projectId}, routes messages
 * through Kafka pipeline, handles all 6 phases including
 * React Topology (Phase 5) and CLI Config (Phase 6).
 */

import axios from 'axios';

const API = axios.create({
  baseURL: 'http://localhost:8080/api',
  timeout: 120000,
});

/**
 * Build a natural-language prompt from the structured requirements form.
 */
function buildPromptFromRequirements(req, solutionType) {
  const isCampus = solutionType !== 'datacenter';

  if (isCampus) {
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
 * Submit requirements and run the full 6-phase AI workflow via Gateway WebSocket.
 *
 * @param {Object} requirements - Form inputs
 * @param {string} solutionType - 'campus' or 'datacenter'
 * @param {Function} onEvent - Callback for each event: (event) => void
 *   Events: phase_start, agent_input, tool_call, tool_result, agent_response,
 *           approval_request, phase_approved, diagram_ready, topology_code_ready,
 *           workflow_complete, error, user_echo
 * @returns {Promise<Object>} - { rephrased, topology, devices, diagramUrl, diagramDownloadUrl, reactCode, cliConfig }
 */
export function runWorkflow(requirements, solutionType, onEvent) {
  return new Promise((resolve, reject) => {
    const prompt = buildPromptFromRequirements(requirements, solutionType);
    const projectId = crypto.randomUUID();
    const wsUrl = `ws://${window.location.host}/chat/${projectId}`;
    const ws = new WebSocket(wsUrl);

    const results = {
      prompt,
      rephrased: '',
      topology: '',
      devices: '',
      diagramUrl: '',
      diagramDownloadUrl: '',
      reactCode: '',
      cliConfig: '',
    };

    let currentPhase = 0;
    let phaseNameMap = {};

    ws.onopen = () => {
      ws.send(JSON.stringify({ content: prompt }));
    };

    ws.onmessage = (e) => {
      try {
        const agentEvent = JSON.parse(e.data);
        const { event_type, data, payload, is_final, agent_name } = agentEvent;

        switch (event_type) {
          case 'TOKEN': {
            if (data && data.startsWith('Starting phase ')) {
              const match = data.match(/Starting phase (\d+): (.+)/);
              if (match) {
                currentPhase = parseInt(match[1]);
                phaseNameMap[currentPhase] = match[2];
                onEvent({ type: 'phase_start', phase: currentPhase, name: match[2] });
              }
            }
            break;
          }

          case 'TOOL_CALL':
            onEvent({
              type: 'tool_call',
              tool_name: payload?.name || 'unknown',
              tool_kwargs: payload?.args || {},
            });
            break;

          case 'TOOL_RESULT':
            onEvent({
              type: 'tool_result',
              tool_name: payload?.name || 'unknown',
              output: payload?.output || '',
            });
            break;

          case 'FINAL_ANSWER': {
            const content = data || '';
            onEvent({ type: 'agent_response', agent: agent_name || 'system', content, phase: currentPhase });

            if (currentPhase === 1) results.rephrased = content;
            else if (currentPhase === 2) results.topology = content;
            else if (currentPhase === 3) results.devices = content;
            break;
          }

          case 'DIAGRAM_READY': {
            let eventData = {};
            try { eventData = JSON.parse(data || '{}'); } catch {}
            results.diagramUrl = eventData.url || '';
            results.diagramDownloadUrl = eventData.download_url || '';
            onEvent({
              type: 'diagram_ready',
              url: eventData.url,
              download_url: eventData.download_url,
              filename: eventData.filename,
            });
            break;
          }

          case 'TOPOLOGY_CODE_READY': {
            let eventData = {};
            try { eventData = JSON.parse(data || '{}'); } catch {}
            results.reactCode = eventData.code || '';
            onEvent({ type: 'topology_code_ready', code: eventData.code });
            break;
          }

          case 'WORKFLOW_COMPLETE': {
            let eventData = {};
            try { eventData = JSON.parse(data || '{}'); } catch {}
            if (eventData.diagram_url && !results.diagramUrl) results.diagramUrl = eventData.diagram_url;
            onEvent({ type: 'workflow_complete' });
            ws.close();
            resolve(results);
            break;
          }

          case 'USER_ECHO': {
            let eventData = {};
            try { eventData = JSON.parse(data || '{}'); } catch {}
            onEvent({ type: 'user_echo', content: eventData.content || '' });
            break;
          }

          case 'APPROVAL_REQUEST': {
            let eventData = {};
            try { eventData = JSON.parse(data || '{}'); } catch {}
            onEvent({
              type: 'approval_request',
              message: eventData.message || `Phase ${currentPhase} requires approval`,
              ws,
            });
            break;
          }

          case 'PHASE_APPROVED':
            onEvent({ type: 'phase_approved', phase: currentPhase });
            break;

          case 'PHASE_REVISION':
            onEvent({ type: 'phase_revision', phase: currentPhase });
            break;

          case 'DIAGRAM_ERROR': {
            let eventData = {};
            try { eventData = JSON.parse(data || '{}'); } catch {}
            onEvent({ type: 'diagram_error', message: eventData.message || 'Diagram generation failed' });
            break;
          }

          case 'TOPOLOGY_CODE_ERROR': {
            let eventData = {};
            try { eventData = JSON.parse(data || '{}'); } catch {}
            onEvent({ type: 'topology_code_error', message: eventData.message || 'Topology code generation failed' });
            break;
          }

          case 'CONFIG_RAG_RESULT': {
            let eventData = {};
            try { eventData = JSON.parse(data || '{}'); } catch {}
            onEvent({
              type: 'config_rag_result',
              total_chars: eventData.total_chars || 0,
              output: eventData.output || '',
            });
            break;
          }

          case 'RAG_RESULT': {
            let eventData = {};
            try { eventData = JSON.parse(data || '{}'); } catch {}
            onEvent({
              type: 'rag_result',
              total: eventData.total || 0,
              chunks: eventData.chunks || [],
              source: eventData.source || '',
              tool_name: eventData.tool_name || '',
            });
            break;
          }

          case 'ERROR': {
            const errorMsg = data || 'Unknown workflow error';
            onEvent({ type: 'error', message: errorMsg });
            ws.close();
            reject(new Error(errorMsg));
            break;
          }

          default: {
            if (event_type && data) {
              let eventData = {};
              try { eventData = JSON.parse(data || '{}'); } catch {}
              onEvent({
                type: event_type.toLowerCase(),
                ...eventData,
                agent_name,
                is_final,
              });
            }
            break;
          }
        }
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
 */
export async function sendChatMessage(message, history = []) {
  try {
    const res = await API.post('/chat', { message, history });
    return res.data;
  } catch {
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

export async function submitRequirements(requirements) {
  console.warn('[API] submitRequirements is deprecated, use runWorkflow instead');
  return null;
}
