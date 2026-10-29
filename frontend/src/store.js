import { create } from "zustand";
import { addEdge, applyEdgeChanges, applyNodeChanges, MarkerType } from "reactflow";

import * as api from "./api";
import { NODE_DEFINITIONS, createNodeData } from "./nodes/definitions";
import {
  applyTheme,
  extractVariables,
  readJSONStorage,
  readStorage,
  serializeGraph,
  writeStorage,
} from "./utils";

const HISTORY_LIMIT = 50;
const EDGE_DEFAULTS = { type: "smoothstep", markerEnd: { type: MarkerType.ArrowClosed } };
const UNTITLED = "Untitled Workflow";

let runController = null;
let lastSnapshotAt = 0;
let lastFieldEdit = { key: null, at: 0 };
let toastSeq = 0;

/** Add the current graph to the undo stack. Calls within 50ms count as one user action. */
const withSnapshot = (state, patch) => {
  const now = Date.now();
  if (now - lastSnapshotAt < 50) return patch;
  lastSnapshotAt = now;
  return {
    ...patch,
    history: [...state.history.slice(-(HISTORY_LIMIT - 1)), { nodes: state.nodes, edges: state.edges }],
    future: [],
  };
};

const touched = (state) => ({ dirty: true, graphVersion: state.graphVersion + 1 });

const hydrateNodes = (nodes = []) =>
  nodes.map((node) => ({
    id: node.id,
    type: node.type,
    position: node.position ?? { x: 0, y: 0 },
    data: { ...createNodeData(node.type), ...(node.data ?? {}) },
  }));

const hydrateEdges = (edges = []) => edges.map((edge) => ({ ...EDGE_DEFAULTS, ...edge }));

const rebuildCounters = (nodes) => {
  const counters = {};
  nodes.forEach((node) => {
    const match = /^(.+)-(\d+)$/.exec(String(node.id));
    if (match) counters[match[1]] = Math.max(counters[match[1]] ?? 0, Number(match[2]));
  });
  return counters;
};

const emptyRun = { runStatus: "idle", runError: null, runOutputs: {}, runOrder: [], runSummary: null, nodeResults: {} };

const initialDark = () => {
  const stored = readStorage("nexflow-dark");
  if (stored !== null) return stored === "1";
  return Boolean(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
};

export const useStore = create((set, get) => ({
  // ------------------------------------------------------------- graph ----
  nodes: [],
  edges: [],
  nodeIDs: {},
  history: [],
  future: [],
  workflowId: null,
  workflowName: UNTITLED,
  dirty: false,
  graphVersion: 0,
  viewVersion: 0,

  confirmDiscard: () => !get().dirty || window.confirm("You have unsaved changes. Discard them?"),

  setWorkflowName: (workflowName) => set((state) => ({ workflowName, ...touched(state) })),

  addNodeOfType: (type, position) => {
    if (!NODE_DEFINITIONS[type]) return null;
    let createdId = null;
    set((state) => {
      let counter = (state.nodeIDs[type] ?? 0) + 1;
      while (state.nodes.some((n) => n.id === `${type}-${counter}`)) counter += 1;
      createdId = `${type}-${counter}`;
      const node = { id: createdId, type, position, data: createNodeData(type) };
      return withSnapshot(state, {
        nodes: [...state.nodes.map((n) => (n.selected ? { ...n, selected: false } : n)), { ...node, selected: true }],
        nodeIDs: { ...state.nodeIDs, [type]: counter },
        ...touched(state),
      });
    });
    return createdId;
  },

  pushHistory: () => set((state) => withSnapshot(state, {})),

  onNodesChange: (changes) =>
    set((state) => {
      const patch = { nodes: applyNodeChanges(changes, state.nodes) };
      if (changes.some((c) => c.type === "remove")) Object.assign(patch, withSnapshot(state, {}));
      if (changes.some((c) => c.type !== "select" && c.type !== "dimensions")) Object.assign(patch, touched(state));
      return patch;
    }),

  onEdgesChange: (changes) =>
    set((state) => {
      const patch = { edges: applyEdgeChanges(changes, state.edges) };
      if (changes.some((c) => c.type === "remove")) Object.assign(patch, withSnapshot(state, {}), touched(state));
      return patch;
    }),

  isValidConnection: (connection) => {
    const { nodes, edges } = get();
    const { source, target, sourceHandle, targetHandle } = connection;
    if (!source || !target || source === target) return false;
    if (!nodes.some((n) => n.id === source) || !nodes.some((n) => n.id === target)) return false;
    if (edges.some((e) => e.source === source && e.target === target &&
        (e.sourceHandle ?? null) === (sourceHandle ?? null) && (e.targetHandle ?? null) === (targetHandle ?? null))) {
      return false;
    }
    // Reject connections that would create a cycle: target must not already reach source.
    const children = {};
    edges.forEach((e) => (children[e.source] = [...(children[e.source] ?? []), e.target]));
    const stack = [target];
    const seen = new Set();
    while (stack.length) {
      const current = stack.pop();
      if (current === source) return false;
      if (seen.has(current)) continue;
      seen.add(current);
      stack.push(...(children[current] ?? []));
    }
    return true;
  },

  onConnect: (connection) => {
    if (!get().isValidConnection(connection)) return;
    set((state) =>
      withSnapshot(state, { edges: addEdge({ ...EDGE_DEFAULTS, ...connection }, state.edges), ...touched(state) })
    );
  },

  updateNodeField: (nodeId, field, value) =>
    set((state) => {
      const now = Date.now();
      const key = `${nodeId}:${field}`;
      const startsNewEdit = lastFieldEdit.key !== key || now - lastFieldEdit.at > 1500;
      lastFieldEdit = { key, at: now };

      let edges = state.edges;
      const target = state.nodes.find((n) => n.id === nodeId);
      if (target && target.type === "text" && field === "text") {
        const variables = extractVariables(value);
        edges = edges.filter((e) => e.target !== nodeId || variables.includes(e.targetHandle));
      }
      const patch = {
        nodes: state.nodes.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, [field]: value } } : n)),
        edges,
        ...touched(state),
      };
      return startsNewEdit ? withSnapshot(state, patch) : patch;
    }),

  undo: () =>
    set((state) => {
      if (!state.history.length) return state;
      const previous = state.history[state.history.length - 1];
      return {
        nodes: previous.nodes,
        edges: previous.edges,
        history: state.history.slice(0, -1),
        future: [{ nodes: state.nodes, edges: state.edges }, ...state.future].slice(0, HISTORY_LIMIT),
        ...touched(state),
      };
    }),

  redo: () =>
    set((state) => {
      if (!state.future.length) return state;
      const [next, ...rest] = state.future;
      return {
        nodes: next.nodes,
        edges: next.edges,
        future: rest,
        history: [...state.history, { nodes: state.nodes, edges: state.edges }].slice(-HISTORY_LIMIT),
        ...touched(state),
      };
    }),

  // --------------------------------------------------------- workflows ----
  saveStatus: "idle",

  newWorkflow: () => {
    get().cancelRun();
    set({
      nodes: [], edges: [], nodeIDs: {}, history: [], future: [], workflowId: null,
      workflowName: UNTITLED, dirty: false, graphVersion: 0, analysis: null, panelOpen: false, ...emptyRun,
    });
  },

  loadWorkflow: (workflow) => {
    get().cancelRun();
    const nodes = hydrateNodes(workflow.nodes);
    set({
      nodes,
      edges: hydrateEdges(workflow.edges),
      nodeIDs: rebuildCounters(nodes),
      history: [],
      future: [],
      workflowId: workflow.id,
      workflowName: workflow.name || UNTITLED,
      dirty: false,
      graphVersion: 0,
      viewVersion: get().viewVersion + 1,
      analysis: null,
      panelOpen: false,
      ...emptyRun,
    });
  },

  saveWorkflow: async () => {
    const { saveStatus, nodes, edges, workflowId, workflowName, graphVersion, notify } = get();
    if (saveStatus === "saving") return;
    set({ saveStatus: "saving" });
    const payload = { name: workflowName.trim() || UNTITLED, ...serializeGraph(nodes, edges) };
    try {
      const saved = workflowId ? await api.updateWorkflow(workflowId, payload) : await api.createWorkflow(payload);
      set((state) => ({
        workflowId: saved.id,
        workflowName: saved.name,
        dirty: state.graphVersion !== graphVersion,
        saveStatus: "saved",
      }));
      notify("success", "Workflow saved");
      setTimeout(() => set((state) => (state.saveStatus === "saved" ? { saveStatus: "idle" } : {})), 1800);
    } catch (error) {
      set({ saveStatus: "error" });
      notify("error", `Could not save: ${error.message}`);
      setTimeout(() => set((state) => (state.saveStatus === "error" ? { saveStatus: "idle" } : {})), 3000);
    }
  },

  // --------------------------------------------------------- execution ----
  ...emptyRun,
  panelOpen: false,
  analysis: null,
  analyzing: false,

  setPanelOpen: (panelOpen) => set({ panelOpen }),

  runWorkflow: async () => {
    const { nodes, edges, runStatus, notify } = get();
    if (runStatus === "running") return;
    if (!nodes.length) {
      notify("info", "Add some nodes before running.");
      return;
    }
    runController = new AbortController();
    const controller = runController;
    const pending = {};
    nodes.forEach((n) => (pending[n.id] = { status: "pending" }));
    set({ ...emptyRun, runStatus: "running", nodeResults: pending, panelOpen: true });

    const patchResult = (id, result) =>
      set((state) => ({ nodeResults: { ...state.nodeResults, [id]: { ...state.nodeResults[id], ...result } } }));

    const onEvent = (name, data) => {
      if (name === "start") set({ runOrder: data.execution_order });
      else if (name === "node_start") patchResult(data.node_id, { status: "running", position: data.position });
      else if (name === "node_complete" || name === "node_error" || name === "node_skipped") {
        patchResult(data.node_id, data);
      } else if (name === "error") set({ runStatus: "failed", runError: data.detail });
      else if (name === "done") {
        set({
          runStatus: data.status === "success" ? "success" : "failed",
          runError: data.error ?? null,
          runOutputs: data.outputs ?? {},
          runSummary: { duration_ms: data.duration_ms, executed: data.nodes_executed, skipped: data.nodes_skipped },
        });
      }
    };

    try {
      await api.streamExecute(serializeGraph(nodes, edges), { signal: controller.signal, onEvent });
      if (get().runStatus === "running") {
        set({ runStatus: "failed", runError: "The connection closed before the workflow finished." });
      }
    } catch (error) {
      if (error.name === "AbortError") return;
      set({ runStatus: "failed", runError: error.message });
      notify("error", error.message);
    } finally {
      // Cancelled or superseded runs were already cleaned up by cancelRun / the newer run.
      if (runController !== controller) return;
      runController = null;
      // Nodes that never ran must not look stuck as "pending" or "running".
      set((state) => {
        const cleaned = {};
        Object.entries(state.nodeResults).forEach(([id, r]) => {
          cleaned[id] = r.status === "pending" || r.status === "running" ? { ...r, status: state.runStatus === "failed" ? "skipped" : r.status } : r;
        });
        return { nodeResults: cleaned };
      });
    }
  },

  cancelRun: () => {
    if (!runController) return;
    runController.abort();
    runController = null;
    set((state) => {
      const cleaned = {};
      Object.entries(state.nodeResults).forEach(([id, r]) => {
        if (r.status !== "pending" && r.status !== "running") cleaned[id] = r;
      });
      return { runStatus: "cancelled", runError: "Run cancelled.", nodeResults: cleaned };
    });
  },

  clearRun: () => set({ ...emptyRun, panelOpen: false }),

  analyze: async () => {
    const { nodes, edges, notify } = get();
    set({ analyzing: true });
    try {
      const analysis = await api.analyzeGraph(serializeGraph(nodes, edges));
      set({ analysis });
    } catch (error) {
      notify("error", `Analysis failed: ${error.message}`);
    } finally {
      set({ analyzing: false });
    }
  },

  closeAnalysis: () => set({ analysis: null }),

  // -------------------------------------------------------------- theme ----
  darkMode: initialDark(),
  toggleDarkMode: () =>
    set((state) => {
      const darkMode = !state.darkMode;
      writeStorage("nexflow-dark", darkMode ? "1" : "0");
      applyTheme(darkMode);
      return { darkMode };
    }),

  // -------------------------------------------------------------- toasts ----
  toasts: [],
  notify: (kind, message) => {
    toastSeq += 1;
    const id = toastSeq;
    set((state) => ({ toasts: [...state.toasts.slice(-3), { id, kind, message }] }));
    setTimeout(() => get().dismissToast(id), kind === "error" ? 6000 : 3500);
  },
  dismissToast: (id) => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),

  // --------------------------------------------------------------- auth ----
  token: readStorage("nexflow-token"),
  user: readJSONStorage("nexflow-user"),
  config: null,
  authReady: false,

  initApp: async () => {
    try {
      set({ config: await api.getConfig() });
    } catch (error) {
      get().notify("error", error.message);
    }
    if (get().token) {
      try {
        const user = await api.getMe();
        writeStorage("nexflow-user", JSON.stringify(user));
        set({ user });
      } catch (error) {
        if (error.status === 401) get().logout();
      }
    }
    set({ authReady: true });
  },

  completeAuth: ({ token, user }) => {
    writeStorage("nexflow-token", token);
    writeStorage("nexflow-user", JSON.stringify(user));
    set({ token, user });
  },

  login: async (email, password) => get().completeAuth(await api.login(email, password)),
  register: async (name, email, password) => get().completeAuth(await api.register(name, email, password)),

  updateProfile: async (payload) => get().completeAuth(await api.updateProfile(payload)),
  changePassword: async (current, next) => get().completeAuth(await api.changePassword(current, next)),
  deleteAccount: async (password) => {
    await api.deleteAccount(password);
    get().logout();
  },

  logout: () => {
    get().newWorkflow();
    writeStorage("nexflow-token", null);
    writeStorage("nexflow-user", null);
    set({ token: null, user: null });
  },
}));

api.configure({
  getToken: () => useStore.getState().token,
  onUnauthorized: () => {
    const { token, logout, notify } = useStore.getState();
    if (token) {
      logout();
      notify("error", "Your session has expired. Please sign in again.");
    }
  },
});
