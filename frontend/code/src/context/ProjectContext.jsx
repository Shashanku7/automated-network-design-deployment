import {
  createContext,
  useContext,
  useReducer,
  useEffect,
  useRef,
  useCallback,
} from "react";
import { saveProjectToDb } from "../services/api";

const ProjectContext = createContext(null);

const INDEX_KEY = "project_index";

function getProjectIndex() {
  try {
    return JSON.parse(localStorage.getItem(INDEX_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveProjectIndex(index) {
  localStorage.setItem(INDEX_KEY, JSON.stringify(index));
}

function loadProjectState(projectId) {
  try {
    const raw = localStorage.getItem(`project_${projectId}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

const initialState = {
  projectId: null,
  conversationId: null,
  projectTitle: "",
  solutionType: null,

  requirements: {
    buildingCount: "",
    buildings: [],
    dcRacks: "",
    dcServers: "",
    specialRoles: [],
    devices: {
      laptops: false,
      printers: false,
      phones: false,
      cameras: false,
      wifi: true,
    },
    sensitiveAreas: [],
    uptimeLevel: "standard",
    expectGrowth: false,
    growthAmount: "",
    additionalNotes: "",
  },

  workflowStatus: "idle",
  currentPhase: 0,
  currentPhaseName: "",
  workflowEvents: [],
  wsRef: null,

  rephrasedPrompt: null,
  topologyDesign: null,
  deviceSelection: null,
  diagramUrl: null,
  diagramDownloadUrl: null,
  cliConfig: null,
  reactCode: null,

  proposedDesign: null,
  chatHistory: [],
  deploymentStatus: "idle",
};

function projectReducer(state, action) {
  switch (action.type) {
    case "LOAD_PROJECT": {
      const projectId = action.payload;
      const index = getProjectIndex();
      const meta = index.find((p) => p.id === projectId);
      const saved = loadProjectState(projectId);
      const base = {
        ...initialState,
        projectId,
        projectTitle: meta?.title || saved?.projectTitle || "",
        conversationId: saved?.conversationId || null,
      };
      if (saved) {
        return {
          ...base,
          solutionType: saved.solutionType ?? null,
          requirements: saved.requirements
            ? { ...base.requirements, ...saved.requirements }
            : base.requirements,
          workflowStatus: saved.workflowStatus ?? "idle",
          currentPhase: saved.currentPhase ?? 0,
          currentPhaseName: saved.currentPhaseName ?? "",
          rephrasedPrompt: saved.rephrasedPrompt ?? null,
          topologyDesign: saved.topologyDesign ?? null,
          deviceSelection: saved.deviceSelection ?? null,
          diagramUrl: saved.diagramUrl ?? null,
          diagramDownloadUrl: saved.diagramDownloadUrl ?? null,
          cliConfig: saved.cliConfig ?? null,
          reactCode: saved.reactCode ?? null,
          proposedDesign: saved.proposedDesign ?? null,
          workflowEvents: saved.workflowEvents ?? [],
          chatHistory: saved.chatHistory ?? [],
          deploymentStatus: saved.deploymentStatus ?? "idle",
        };
      }
      return base;
    }

    case "SET_PROJECT_ID":
      return {
        ...initialState,
        projectId: action.payload.projectId,
        projectTitle: action.payload.projectTitle || "",
      };

    case "SET_CONVERSATION_ID":
      return { ...state, conversationId: action.payload };

    case "SET_SOLUTION_TYPE":
      return { ...state, solutionType: action.payload };

    case "UPDATE_REQUIREMENTS":
      return {
        ...state,
        requirements: { ...state.requirements, ...action.payload },
      };

    case "SET_PROPOSED_DESIGN":
      return {
        ...state,
        proposedDesign: action.payload,
        deploymentStatus: "ready",
      };

    case "SET_CHAT_HISTORY":
      return { ...state, chatHistory: action.payload };

    case "ADD_CHAT_MESSAGE":
      return { ...state, chatHistory: [...state.chatHistory, action.payload] };

    case "SET_DEPLOYMENT_STATUS":
      return { ...state, deploymentStatus: action.payload };

    case "RESET_PROJECT":
      return { ...initialState };

    case "WORKFLOW_START":
      return {
        ...state,
        workflowStatus: "running",
        currentPhase: 0,
        workflowEvents: [],
        rephrasedPrompt: null,
        topologyDesign: null,
        deviceSelection: null,
        diagramUrl: null,
        diagramDownloadUrl: null,
        cliConfig: null,
        reactCode: null,
      };

    case "WORKFLOW_EVENT":
      return {
        ...state,
        workflowEvents: [
          ...state.workflowEvents,
          {
            ...action.payload,
            timestamp: Date.now(),
            _id:
              action.payload._id ||
              `${action.payload.type}|${action.payload.phase || ""}|${action.payload.content || ""}|${action.payload.tool_name || ""}`,
          },
        ],
      };

    case "SET_WORKFLOW_EVENTS":
      return { ...state, workflowEvents: action.payload };

    case "PHASE_START":
      return {
        ...state,
        currentPhase: action.payload.phase,
        currentPhaseName: action.payload.name,
        workflowStatus: "running",
      };

    case "SET_REPHRASED":
      return { ...state, rephrasedPrompt: action.payload };

    case "SET_TOPOLOGY":
      return { ...state, topologyDesign: action.payload };

    case "SET_DEVICES":
      return { ...state, deviceSelection: action.payload };

    case "AWAITING_APPROVAL":
      return {
        ...state,
        workflowStatus: "awaiting_approval",
        wsRef: action.payload.ws,
      };

    case "SET_DIAGRAM":
      return {
        ...state,
        diagramUrl: action.payload.url,
        diagramDownloadUrl: action.payload.downloadUrl,
      };

    case "SET_CLI_CONFIG":
      return { ...state, cliConfig: action.payload };

    case "WORKFLOW_COMPLETE":
      return { ...state, workflowStatus: "complete", wsRef: null };

    case "WORKFLOW_ERROR":
      return { ...state, workflowStatus: "error", wsRef: null };

    case "SET_REACT_CODE":
      return { ...state, reactCode: action.payload };

    default:
      return state;
  }
}

export function ProjectProvider({ children }) {
  const [state, dispatch] = useReducer(projectReducer, initialState);
  const lastSavedRef = useRef("");

  const updateProjectMeta = useCallback((id, updates) => {
    const index = getProjectIndex().map((p) =>
      p.id === id
        ? { ...p, ...updates, updatedAt: new Date().toISOString() }
        : p,
    );
    saveProjectIndex(index);
  }, []);

  // Sync workflowStatus to project index for dashboard
  useEffect(() => {
    if (!state.projectId) return;
    const map = {
      running: "designing",
      awaiting_approval: "designing",
      complete: "complete",
      error: "designing",
    };
    const s = map[state.workflowStatus];
    if (s) updateProjectMeta(state.projectId, { status: s });
  }, [state.workflowStatus, state.projectId, updateProjectMeta]);

  useEffect(() => {
    if (!state.projectId) return;
    const persistable = {
      projectId: state.projectId,
      conversationId: state.conversationId,
      chatHistory: state.chatHistory,
      projectTitle: state.projectTitle,
      solutionType: state.solutionType,
      requirements: state.requirements,
      workflowEvents: state.workflowEvents,
      workflowStatus: state.workflowStatus,
      currentPhase: state.currentPhase,
      currentPhaseName: state.currentPhaseName,
      rephrasedPrompt: state.rephrasedPrompt,
      topologyDesign: state.topologyDesign,
      deviceSelection: state.deviceSelection,
      diagramUrl: state.diagramUrl,
      diagramDownloadUrl: state.diagramDownloadUrl,
      cliConfig: state.cliConfig,
      reactCode: state.reactCode,
      proposedDesign: state.proposedDesign,
      chatHistory: state.chatHistory,
      deploymentStatus: state.deploymentStatus,
    };
    const serialized = JSON.stringify(persistable);
    if (serialized !== lastSavedRef.current) {
      lastSavedRef.current = serialized;
      localStorage.setItem(`project_${state.projectId}`, serialized);
      // Also persist to PostgreSQL
      saveProjectToDb(state.projectId, {
        title: state.projectTitle,
        solutionType: state.solutionType,
        requirements: state.requirements,
        chatHistory: state.chatHistory,
        workflowStatus: state.workflowStatus,
      });
    }
  }, [state]);

  const createProject = useCallback((title) => {
    const id = crypto.randomUUID();
    const now = new Date().toISOString();
    const index = getProjectIndex();
    index.unshift({
      id,
      title,
      createdAt: now,
      updatedAt: now,
      status: "draft",
    });
    saveProjectIndex(index);
    dispatch({
      type: "SET_PROJECT_ID",
      payload: { projectId: id, projectTitle: title },
    });
    return id;
  }, []);

  const loadProject = useCallback((id) => {
    dispatch({ type: "LOAD_PROJECT", payload: id });
  }, []);

  const getProjectList = useCallback(() => getProjectIndex(), []);

  const deleteProject = useCallback(
    (id) => {
      const index = getProjectIndex().filter((p) => p.id !== id);
      saveProjectIndex(index);
      localStorage.removeItem(`project_${id}`);
      if (state.projectId === id) dispatch({ type: "RESET_PROJECT" });
    },
    [state.projectId],
  );

  return (
    <ProjectContext.Provider
      value={{
        state,
        dispatch,
        createProject,
        loadProject,
        getProjectList,
        deleteProject,
        updateProjectMeta,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  const context = useContext(ProjectContext);
  if (!context)
    throw new Error("useProject must be used within a ProjectProvider");
  return context;
}
