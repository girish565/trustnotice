const tok = () => localStorage.getItem("tn_token");
const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
export const apiUrl = (path) => `${API_BASE}${path}`;
export const websocketUrl = (path, params = {}) => {
  const base = API_BASE ? API_BASE.replace(/^http/, "ws") : `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}`;
  const query = new URLSearchParams(params).toString();
  return `${base}${path}${query ? `?${query}` : ""}`;
};
async function req(path, opts = {}) {
  const headers = { ...(opts.headers || {}) }; if (tok()) headers.Authorization = `Bearer ${tok()}`;
  const r = await fetch(apiUrl(path), { ...opts, headers });
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch {} throw new Error(typeof m === "string" ? m : "Request failed"); }
  return r;
}
const json = async (p, o) => (await req(p, o)).json();
const form = (obj) => {
  const f = new FormData();
  Object.entries(obj).forEach(([key, value]) => {
    if (value == null) return;
    if (Array.isArray(value)) value.forEach((item) => f.append(key, item));
    else f.append(key, value);
  });
  return f;
};
export const api = {
  login: (email, password) => json("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) }),
  me: () => json("/api/auth/me"), stats: () => json("/api/public/stats"),
  verifyUpload: (file, notice_id) => json("/api/verify/upload", { method: "POST", body: form({ file, notice_id }) }),
  verifyQr: (file) => json("/api/verify/qr", { method: "POST", body: form({ file }) }),
  record: (id) => json(`/api/verify/${id}`), notice: (id) => json(`/api/notices/${id}`),
  dashboard: () => json("/api/admin/dashboard"), logs: () => json("/api/admin/verification-logs"), notices: () => json("/api/notices"),
  create: (v) => json("/api/notices/create", { method: "POST", body: form(v) }),
  newVersion: (id, v) => json(`/api/notices/${id}/new-version`, { method: "POST", body: form(v) }),
  keys: () => json("/api/admin/keys"), revokeKey: (id) => json(`/api/admin/keys/${id}/revoke`, { method: "POST" }),
  revoke: (id, reason) => json(`/api/notices/${id}/revoke`, { method: "POST", body: reason ? form({ reason }) : undefined }),
  students: () => json("/api/admin/students"),
  createStudent: (v) => json("/api/admin/students", { method: "POST", body: form(v) }),
  createEmergency: (v) => json("/api/admin/emergencies", { method: "POST", body: form(v) }),
  emergencyAnalytics: () => json("/api/admin/emergency-analytics"),
  audit: () => json("/api/admin/audit-log"),
  notifications: () => json("/api/student/notifications"),
  emergencies: () => json("/api/student/emergencies"),
  socketTicket: () => json("/api/notifications/socket-ticket", { method: "POST" }),
  readNotification: (id) => json(`/api/student/notifications/${id}/read`, { method: "POST" }),
  acknowledgeNotification: (id) => json(`/api/student/notifications/${id}/acknowledge`, { method: "POST" }),
  readAllNotifications: () => json("/api/student/notifications/read-all", { method: "POST" }),
  blobUrl: async (path) => URL.createObjectURL(await (await req(path)).blob()),
};
