import { auth } from "./auth.js";
const BASE = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");
let onUnauthorized = () => {};
export const setUnauthorizedHandler = (fn) => {
  onUnauthorized = fn;
};

async function request(path, options = {}) {
  const token = auth.getToken();
  const { headers, ...rest } = options;
  let response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...rest,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(headers || {}),
      },
    });
  } catch {
    throw new Error(
      `Cannot connect to ${BASE}. Start the FastAPI backend and check its CORS settings.`,
    );
  }
  const type = response.headers.get("content-type") || "";
  const data = type.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    // An expired or invalid token on a normal request sends the person back to login.
    if (response.status === 401 && token && !path.startsWith("/auth/"))
      onUnauthorized();
    const detail =
      typeof data === "object" && data?.detail
        ? Array.isArray(data.detail)
          ? data.detail.map((x) => x.msg || JSON.stringify(x)).join(", ")
          : data.detail
        : `Request failed (${response.status})`;
    throw new Error(detail);
  }
  return data;
}
export const api = {
  signup: ({ name, email, password }) =>
    request("/auth/signup", {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    }),
  login: ({ email, password }) =>
    request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request("/auth/me"),
  health: () => request("/health"),
  analyze: (message) =>
    request("/tickets/analyze", {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  importFile: async (file) => {
    const token = auth.getToken();
    const form = new FormData();
    form.append("file", file);
    let response;
    try {
      response = await fetch(
        `${BASE}/tickets/import/${file.name.toLowerCase().endsWith(".csv") ? "csv" : "json"}`,
        {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: form,
        },
      );
    } catch {
      throw new Error(
        `Cannot connect to ${BASE}. Start the FastAPI backend and check its CORS settings.`,
      );
    }
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) onUnauthorized();
    if (!response.ok)
      throw new Error(data?.detail || `Import failed (${response.status})`);
    return data;
  },
  tickets: () => request("/tickets?limit=100&offset=0"),
  analytics: () => request("/analytics"),
  activity: (limit = 200, offset = 0) =>
    request(`/activity?limit=${limit}&offset=${offset}`),
  resolveTicket: (id) =>
    request(`/tickets/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "resolved" }),
    }),
  reopenTicket: (id) =>
    request(`/tickets/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "open" }),
    }),
  deleteTicket: (id) => request(`/tickets/${id}`, { method: "DELETE" }),
  exportFile: async (format) => {
    let response;
    try {
      response = await fetch(`${BASE}/tickets/export/${format}`, {
        headers: auth.getToken()
          ? { Authorization: `Bearer ${auth.getToken()}` }
          : {},
      });
    } catch {
      throw new Error(`Cannot connect to ${BASE}.`);
    }
    if (response.status === 401) onUnauthorized();
    if (!response.ok) throw new Error(`Export failed (${response.status})`);
    return response.blob();
  },
};
