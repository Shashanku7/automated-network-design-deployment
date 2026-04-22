/**
 * API Service Layer — Stubs for Backend & AI Integration
 * 
 * All functions return mock data for the prototype.
 * Each function has a clear TODO for the backend/AI team to replace
 * with real HTTP calls via Axios.
 * 
 * Base URL should point to the FastAPI/Quarkus backend when ready.
 */

import axios from 'axios';

// TODO: Update this to the real backend URL when deployed
const API = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 10000,
});

/**
 * Submit user requirements and get a proposed network design.
 * Called after the Requirements form is submitted.
 * 
 * @param {Object} requirements - The simplified user inputs
 * @returns {Object} - Proposed design with topology, summary, BOM
 */
export async function submitRequirements(requirements) {
  // TODO: Connect to real backend — POST /api/requirements
  // The backend will forward this to the AI engine (RAG + LLM)
  console.log('[API STUB] submitRequirements called with:', requirements);
  
  // Mock response simulating what the AI would return
  return {
    summary: `Based on your inputs, we recommend a network design for ${requirements.buildings || 1} building(s) supporting ${requirements.students || 0} users with ${requirements.sensitiveAreas?.length || 0} secured zones.`,
    topology: {
      nodes: [
        { id: 'core', label: 'Core Switch', type: 'switch', model: 'Aruba CX 6300' },
        { id: 'dist1', label: 'Building 1 Switch', type: 'switch', model: 'Aruba CX 6200' },
        { id: 'dist2', label: 'Building 2 Switch', type: 'switch', model: 'Aruba CX 6200' },
        { id: 'ap1', label: 'Wi-Fi Access Points', type: 'wireless', model: 'Aruba AP-635' },
        { id: 'gw', label: 'Gateway', type: 'gateway', model: 'Aruba 9004 Gateway' },
      ],
      links: [
        { from: 'gw', to: 'core' },
        { from: 'core', to: 'dist1' },
        { from: 'core', to: 'dist2' },
        { from: 'dist1', to: 'ap1' },
      ]
    },
    bom: [
      { product: 'Aruba CX 6300M Switch', category: 'Core Switch', qty: 1, purpose: 'Main backbone switch connecting all buildings' },
      { product: 'Aruba CX 6200F 24G Switch', category: 'Access Switch', qty: requirements.buildings || 2, purpose: 'One per building for device connections' },
      { product: 'Aruba AP-635 Access Point', category: 'Wireless', qty: Math.ceil((requirements.students || 100) / 30), purpose: 'Wi-Fi coverage for users' },
      { product: 'Aruba 9004 Gateway', category: 'Gateway', qty: 1, purpose: 'Secure network entry point and policy enforcement' },
      { product: 'Cat6A Cabling Kit', category: 'Cabling', qty: requirements.buildings || 2, purpose: 'Inter-building and intra-building wiring' },
    ]
  };
}

/**
 * Send a message to the Grounded Design Copilot (AI chatbot).
 * The chatbot should already have context from the submitted requirements.
 * 
 * @param {string} message - User's chat message
 * @param {Array} history - Previous chat messages for context
 * @returns {Object} - AI response
 */
export async function sendChatMessage(message, history = []) {
  // TODO: [AI TEAM]
  // Connect to your RAG-based chatbot service.
  // The service should use the Aruba documentation vector DB (e.g., Qdrant/Pinecone).
  // Request: POST /api/chat { message, history, context: currentProjectState }
  console.log('[API STUB] sendChatMessage:', message);

  return {
    role: 'assistant',
    content: `Thank you for your question about "${message}". In the final system, this response will come from the Grounded Design Copilot powered by RAG over HPE Aruba documentation. For now, this is a placeholder response.`,
    timestamp: new Date().toISOString(),
  };
}

/**
 * Trigger the deployment process.
 * 
 * TODO: [BACKEND TEAM]
 * Connect this to your orchestration pipeline (e.g., Kafka / Aruba Central API).
 */
export async function triggerDeployment(projectId) {
  // TODO: [BACKEND TEAM] — POST /api/deploy
  console.log('[API STUB] triggerDeployment for project:', projectId);

  return {
    status: 'success',
    message: 'Deployment initiated. Configuration is being pushed to network devices.',
    projectId,
  };
}
