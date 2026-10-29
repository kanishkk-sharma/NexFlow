const BASE = (process.env.REACT_APP_API_URL || "").replace(/\/$/, "");

let hooks = { getToken: () => null, onUnauthorized: () => {} };

/** The store registers token access and the 401 handler here (avoids a circular import). */
export const configure = (next) => {
  hooks = next;
};

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const describeError = (data, status) => {
  const detail = data && data.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((item) => {
        const field = Array.isArray(item.loc) ? item.loc.filter((p) => p !== "body").join(".") : "";
        const message = String(item.msg || "Invalid value").replace(/^Value error, /, "");
        return field ? `${field}: ${message}` : message;
      })
      .join("; ");
  }
  if (status === 413) return "The workflow is too large.";
  if (status === 429) return "Too many requests. Please wait a moment.";
  if (status >= 500) return "The server hit an unexpected error.";
  return `Request failed (HTTP ${status})`;
};

async function rawFetch(path, { method = "GET", body, signal, auth = true, accept = "application/json" } = {}) {
  const headers = { Accept: accept };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = auth ? hooks.getToken() : null;
  if (token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${BASE}/api${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError("Cannot reach the NexFlow server. Check that the backend is running.", 0);
  }

  if (!response.ok) {
    let data = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }
    if (response.status === 401 && auth) hooks.onUnauthorized();
    throw new ApiError(describeError(data, response.status), response.status);
  }
  return response;
}

async function request(path, options) {
  const response = await rawFetch(path, options);
  return response.status === 204 ? null : response.json();
}

export const getConfig = () => request("/config", { auth: false });
export const getMe = () => request("/auth/me");
export const login = (email, password) =>
  request("/auth/login", { method: "POST", body: { email, password }, auth: false });
export const register = (name, email, password) =>
  request("/auth/register", { method: "POST", body: { name, email, password }, auth: false });

export const updateProfile = (payload) => request("/auth/me", { method: "PATCH", body: payload });
export const changePassword = (current_password, new_password) =>
  request("/auth/change-password", { method: "POST", body: { current_password, new_password } });
export const deleteAccount = (password) => request("/auth/me", { method: "DELETE", body: { password } });

export const listWorkflows = () => request("/workflows");
export const getWorkflow = (id) => request(`/workflows/${encodeURIComponent(id)}`);
export const createWorkflow = (payload) => request("/workflows", { method: "POST", body: payload });
export const updateWorkflow = (id, payload) =>
  request(`/workflows/${encodeURIComponent(id)}`, { method: "PUT", body: payload });
export const deleteWorkflow = (id) => request(`/workflows/${encodeURIComponent(id)}`, { method: "DELETE" });

export const analyzeGraph = (graph) => request("/pipelines/parse", { method: "POST", body: graph });

/**
 * Execute a workflow and stream Server-Sent Events.
 * onEvent(name, data) is called for each event; resolves when the stream ends.
 */
export async function streamExecute(graph, { signal, onEvent }) {
  const response = await rawFetch("/workflows/execute", {
    method: "POST",
    body: { ...graph, stream: true },
    signal,
    accept: "text/event-stream",
  });
  if (!response.body) throw new ApiError("Streaming is not supported by this browser.", 0);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (block) => {
    let name = "message";
    const dataLines = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) name = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (!dataLines.length) return;
    let payload;
    try {
      payload = JSON.parse(dataLines.join("\n"));
    } catch {
      return; // ignore a malformed event rather than aborting the whole run
    }
    onEvent(name, payload);
  };

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      dispatch(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
    }
  }
  if (buffer.trim()) dispatch(buffer);
}
