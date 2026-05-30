import axios from "axios";

const BASE = process.env.REACT_APP_BACKEND_URL || "";
const TOKEN_KEY = "donas_admin_token";

export const api = axios.create({
  baseURL: BASE + "/api",
  withCredentials: true,
});

api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem(TOKEN_KEY);
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

export const adminAuth = {
  TOKEN_KEY,
  saveToken(t) { localStorage.setItem(TOKEN_KEY, t); },
  clearToken() { localStorage.removeItem(TOKEN_KEY); },
  getToken() { return localStorage.getItem(TOKEN_KEY); },
  async login(username, password) {
    const { data } = await api.post("/admin/auth/login", { username, password });
    this.saveToken(data.token);
    return data.user;
  },
  async me() {
    const { data } = await api.get("/admin/auth/me");
    return data;
  },
  async logout() {
    try { await api.post("/admin/auth/logout"); } catch {}
    this.clearToken();
  },
};

export const dashboardApi = {
  kpis: () => api.get("/admin/dashboard/kpis").then((r) => r.data),
  funnel: () => api.get("/admin/dashboard/funnel").then((r) => r.data),
  locations: () => api.get("/admin/dashboard/locations").then((r) => r.data),
  activity7: () => api.get("/admin/dashboard/activity-7days").then((r) => r.data),
  realtime: () => api.get("/admin/dashboard/realtime").then((r) => r.data),
  accessList: (q = "") => api.get("/admin/dashboard/access-list", { params: q ? { q } : {} }).then((r) => r.data),
  resetKpis: () => api.post("/admin/dashboard/reset-kpis").then((r) => r.data),
};

export const inscriptionsApi = {
  list: ({ q = "", status = "all", limit = 100, offset = 0 } = {}) =>
    api.get("/admin/inscriptions", { params: { q, status, limit, offset } }).then((r) => r.data),
  get: (id) => api.get(`/admin/inscriptions/${id}`).then((r) => r.data),
  remove: (id) => api.delete(`/admin/inscriptions/${id}`).then((r) => r.data),
  clear: () => api.post("/admin/inscriptions/clear").then((r) => r.data),
  exportCsvUrl: ({ q = "", status = "all" } = {}) => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (status && status !== "all") params.set("status", status);
    return `${BASE}/api/admin/inscriptions/export.csv?${params.toString()}`;
  },
  exportTxtUrl: ({ q = "", status = "all" } = {}) => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (status && status !== "all") params.set("status", status);
    return `${BASE}/api/admin/inscriptions/export.txt?${params.toString()}`;
  },
  seedDemo: (count = 8) =>
    api.post("/admin/inscriptions/seed-demo", null, { params: { count } }).then((r) => r.data),
};

export const usersApi = {
  list: () => api.get("/admin/users").then((r) => r.data),
  create: ({ username, password, role }) =>
    api.post("/admin/users", { username, password, role }).then((r) => r.data),
  remove: (username) => api.delete(`/admin/users/${username}`).then((r) => r.data),
};

export const settingsApi = {
  get: () => api.get("/admin/settings").then((r) => r.data),
  savePix: ({ pix_key, pix_recipient_name, pix_recipient_city }) =>
    api.put("/admin/settings/pix", { pix_key, pix_recipient_name, pix_recipient_city }).then((r) => r.data),
  saveTelegram: ({ telegram_bot_token, telegram_chat_id, telegram_enabled }) =>
    api.put("/admin/settings/telegram", { telegram_bot_token, telegram_chat_id, telegram_enabled }).then((r) => r.data),
  testTelegram: () => api.post("/admin/settings/telegram/test").then((r) => r.data),
};
