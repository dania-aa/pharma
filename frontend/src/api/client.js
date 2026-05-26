import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  timeout: 300000,
});

// ── Agent / chat ──────────────────────────────────────────────────────────────
export const sendMessage = (conversationId, message) =>
  api.post("/agent/chat", { conversation_id: conversationId, message }).then((r) => r.data);

export const listConversations = () =>
  api.get("/agent/conversations").then((r) => r.data);

export const getConversation = (id) =>
  api.get(`/agent/conversations/${id}`).then((r) => r.data);

export const deleteConversation = (id) =>
  api.delete(`/agent/conversations/${id}`).then((r) => r.data);

export const getSuggestedQueries = () =>
  api.get("/agent/suggested-queries").then((r) => r.data);

// ── ML / trials ───────────────────────────────────────────────────────────────
export const predictByNctId = (nctId) =>
  api.get(`/trials/predict/${nctId}`).then((r) => r.data);

export const predictCustom = (payload) =>
  api.post("/trials/predict", payload).then((r) => r.data);

export const getBenchmark = (params) =>
  api.get("/trials/benchmark", { params }).then((r) => r.data);

export const getBenchmarkByPhase = () =>
  api.get("/trials/benchmark/by-phase").then((r) => r.data);

export const getBenchmarkByArea = () =>
  api.get("/trials/benchmark/by-area").then((r) => r.data);

export const getModelInfo = () =>
  api.get("/trials/model/info").then((r) => r.data);

export default api;
