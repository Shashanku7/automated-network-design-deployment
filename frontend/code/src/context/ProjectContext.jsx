/**
 * ProjectContext — Global State Management
 * 
 * Holds all user inputs (solution type, requirements, etc.)
 * and AI-generated outputs (proposed design, BOM, chat history).
 * 
 * This ensures data flows seamlessly from the Requirements form
 * to the AI Copilot without the user re-entering anything.
 * 
 * Usage: Wrap <App /> with <ProjectProvider>, then use useProject() in any component.
 */

import { createContext, useContext, useReducer } from 'react';

const ProjectContext = createContext(null);

// Initial state — represents a fresh "New Design" session
const initialState = {
  // Step 1: What type of solution? (campus / datacenter)
  solutionType: null,

  // Step 2: User requirements (all in plain, non-technical terms)
  requirements: {
    buildings: '',
    floorsPerBuilding: '1',
    students: '',
    staff: '',
    admins: '',
    specialRoles: [],         // e.g. ['Principal', 'Exam Controller', 'Finance Head']
    devices: {
      laptops: false,
      printers: false,
      phones: false,
      cameras: false,
      wifi: true,
    },
    sensitiveAreas: [],       // e.g. ['Finance Office', 'Examination Cell']
    uptimeLevel: 'standard',  // 'standard' | 'important' | 'critical'
    expectGrowth: false,
    growthAmount: '',
    additionalNotes: '',      // Free-text box for user to describe anything
  },

  // AI-generated outputs (filled after form submission)
  proposedDesign: null,       // { summary, topology, bom }
  chatHistory: [],            // Array of { role, content, timestamp }
  deploymentStatus: 'idle',   // 'idle' | 'ready' | 'executing' | 'complete'
};

// Reducer — handles all state transitions
function projectReducer(state, action) {
  switch (action.type) {
    case 'SET_SOLUTION_TYPE':
      return { ...state, solutionType: action.payload };

    case 'UPDATE_REQUIREMENTS':
      return {
        ...state,
        requirements: { ...state.requirements, ...action.payload },
      };

    case 'SET_PROPOSED_DESIGN':
      return { ...state, proposedDesign: action.payload, deploymentStatus: 'ready' };

    case 'ADD_CHAT_MESSAGE':
      return {
        ...state,
        chatHistory: [...state.chatHistory, action.payload],
      };

    case 'SET_DEPLOYMENT_STATUS':
      return { ...state, deploymentStatus: action.payload };

    case 'RESET_PROJECT':
      return { ...initialState };

    default:
      return state;
  }
}

// Provider component — wraps the app
export function ProjectProvider({ children }) {
  const [state, dispatch] = useReducer(projectReducer, initialState);

  return (
    <ProjectContext.Provider value={{ state, dispatch }}>
      {children}
    </ProjectContext.Provider>
  );
}

// Hook — use this in any component to access state & dispatch
export function useProject() {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error('useProject must be used within a ProjectProvider');
  }
  return context;
}
