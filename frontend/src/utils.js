const VARIABLE_PATTERN = /\{\{\s*([A-Za-z_$][\w$]*)\s*\}\}/g;

/** Unique {{variable}} names in order of first appearance (mirrors the backend regex). */
export const extractVariables = (text) => {
  const names = [];
  for (const match of String(text ?? "").matchAll(VARIABLE_PATTERN)) {
    if (!names.includes(match[1])) names.push(match[1]);
  }
  return names;
};

/** Strip UI-only fields so only what the backend needs is sent or saved. */
export const serializeGraph = (nodes, edges) => ({
  nodes: nodes.map((node) => ({
    id: node.id,
    type: node.type,
    position: { x: node.position.x, y: node.position.y },
    data: node.data,
  })),
  edges: edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.sourceHandle ?? null,
    targetHandle: edge.targetHandle ?? null,
  })),
});

export const readStorage = (key, fallback = null) => {
  try {
    const value = window.localStorage.getItem(key);
    return value === null ? fallback : value;
  } catch {
    return fallback;
  }
};

export const writeStorage = (key, value) => {
  try {
    if (value === null || value === undefined) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    /* storage unavailable (private mode); the app still works for this session */
  }
};

export const readJSONStorage = (key) => {
  try {
    return JSON.parse(readStorage(key, "null"));
  } catch {
    return null;
  }
};

export const applyTheme = (dark) => {
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
};

export const stringifyValue = (value, max = 20000) => {
  let text;
  if (value === undefined) return "";
  if (typeof value === "string") text = value;
  else {
    try {
      text = JSON.stringify(value, null, 2);
    } catch {
      text = String(value);
    }
  }
  return text.length > max ? `${text.slice(0, max)}\n… (${text.length - max} more characters)` : text;
};

export const previewValue = (value, max = 140) => {
  const text = (typeof value === "string" ? value : JSON.stringify(value) ?? "").replace(/\s+/g, " ");
  return text.length > max ? `${text.slice(0, max)}…` : text;
};

export const formatDuration = (ms) => {
  if (ms === undefined || ms === null) return "";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
};

export const isEditableTarget = (target) =>
  Boolean(target && target.closest && target.closest("input, textarea, select, [contenteditable='true']"));
