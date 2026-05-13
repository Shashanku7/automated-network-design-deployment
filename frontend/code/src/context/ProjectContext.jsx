/**
 * ProjectContext — Global State Management
 *
 * Holds user inputs, AI-generated outputs, and workflow state
 * including intermediate steps (tool calls, RAG chunks, agent thinking).
 */

import { createContext, useContext, useReducer } from 'react';

const ProjectContext = createContext(null);

const initialState = {
  solutionType: null,

  requirements: {
    // Campus
    buildingCount: '',
    buildings: [], // Array of { id, name, floorCount, floors: [...] }
    
    // Data Center
    dcRacks: '',
    dcServers: '',

    specialRoles: [],         // e.g. ['Principal', 'Exam Controller', 'Finance Head']
    devices: {
      laptops: false,
      printers: false,
      phones: false,
      cameras: false,
      wifi: true,
    },
    sensitiveAreas: [],
    uptimeLevel: 'standard',
    expectGrowth: false,
    growthAmount: '',
    additionalNotes: '',
  },

  // AI workflow state
  workflowStatus: 'idle', // 'idle' | 'running' | 'awaiting_approval' | 'complete' | 'error'
  currentPhase: 0,
  currentPhaseName: '',
  workflowEvents: [],     // Array of { type, ...data } for intermediate steps display
  wsRef: null,            // WebSocket reference for approval

  // Phase outputs (filled as phases complete)
  rephrasedPrompt: null,
  topologyDesign: null,
  deviceSelection: null,
  diagramUrl: null,
  diagramDownloadUrl: null,

  // Legacy compat
  proposedDesign: null,
  chatHistory: [],
  deploymentStatus: 'idle',
};

function projectReducer(state, action) {
  switch (action.type) {
    case 'SET_SOLUTION_TYPE':
      return { ...state, solutionType: action.payload };

    case 'UPDATE_REQUIREMENTS':
      return { ...state, requirements: { ...state.requirements, ...action.payload } };

    case 'SET_PROPOSED_DESIGN':
      return { ...state, proposedDesign: action.payload, deploymentStatus: 'ready' };

    case 'ADD_CHAT_MESSAGE':
      return { ...state, chatHistory: [...state.chatHistory, action.payload] };

    case 'SET_DEPLOYMENT_STATUS':
      return { ...state, deploymentStatus: action.payload };

    case 'RESET_PROJECT':
      return { ...initialState };

    // ── Workflow actions ─────────────────────
    case 'WORKFLOW_START':
      return {
        ...state,
        workflowStatus: 'running',
        currentPhase: 0,
        workflowEvents: [],
        rephrasedPrompt: null,
        topologyDesign: null,
        deviceSelection: null,
        diagramUrl: null,
        diagramDownloadUrl: null,
      };

    case 'WORKFLOW_EVENT':
      return {
        ...state,
        workflowEvents: [...state.workflowEvents, action.payload],
      };

    case 'PHASE_START':
      return {
        ...state,
        currentPhase: action.payload.phase,
        currentPhaseName: action.payload.name,
        workflowStatus: 'running',
      };

    case 'SET_REPHRASED':
      return { ...state, rephrasedPrompt: action.payload };

    case 'SET_TOPOLOGY':
      return { ...state, topologyDesign: action.payload };

    case 'SET_DEVICES':
      return { ...state, deviceSelection: action.payload };

    case 'AWAITING_APPROVAL':
      return { ...state, workflowStatus: 'awaiting_approval', wsRef: action.payload.ws };

    case 'SET_DIAGRAM':
      return { ...state, diagramUrl: action.payload.url, diagramDownloadUrl: action.payload.downloadUrl };

    case 'WORKFLOW_COMPLETE':
      return { ...state, workflowStatus: 'complete', wsRef: null };

    case 'WORKFLOW_ERROR':
      return { ...state, workflowStatus: 'error', wsRef: null };

    default:
      return state;
  }
}

export function ProjectProvider({ children }) {
  const [state, dispatch] = useReducer(projectReducer, initialState);
  return (
    <ProjectContext.Provider value={{ state, dispatch }}>
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  const context = useContext(ProjectContext);
  if (!context) throw new Error('useProject must be used within a ProjectProvider');
  return context;
}
