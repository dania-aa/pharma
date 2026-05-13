require("dotenv").config();
const express = require("express");
const cors = require("cors");
const helmet = require("helmet");
const compression = require("compression");
const morgan = require("morgan");

const logger = require("./middleware/logger");
const { defaultLimiter } = require("./middleware/rateLimiter");
const trialsRouter = require("./routes/trials");
const agentRouter = require("./routes/agent");

const app = express();
const PORT = process.env.PORT || 3000;

// ── Security & middleware ────────────────────────────────────────────────────
app.use(helmet());
app.use(cors({ origin: process.env.CORS_ORIGIN || "*" }));
app.use(compression());
app.use(express.json({ limit: "1mb" }));
app.use(morgan("combined", { stream: { write: (msg) => logger.info(msg.trim()) } }));
app.use(defaultLimiter);

// ── Routes ───────────────────────────────────────────────────────────────────
app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    service: "gateway",
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
  });
});

app.get("/", (req, res) => {
  res.json({
    name: "TrialMind API Gateway",
    version: "1.0.0",
    endpoints: {
      health: "GET /health",
      chat: "POST /api/agent/chat",
      conversations: "GET /api/agent/conversations",
      predict: "POST /api/trials/predict",
      benchmark: "GET /api/trials/benchmark",
      modelInfo: "GET /api/trials/model/info",
    },
  });
});

app.use("/api/trials", trialsRouter);
app.use("/api/agent", agentRouter);

// ── Error handler ─────────────────────────────────────────────────────────
app.use((err, req, res, _next) => {
  const status = err.response?.status || err.status || 500;
  const message = err.response?.data?.detail || err.message || "Internal server error";

  if (status >= 500) {
    logger.error({ err, path: req.path, method: req.method }, "Request error");
  }

  res.status(status).json({ error: message });
});

// ── Start ────────────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  logger.info(`TrialMind Gateway listening on port ${PORT}`);
});

module.exports = app;
