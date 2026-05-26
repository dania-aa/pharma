const express = require("express");
const axios = require("axios");
const { chatLimiter } = require("../middleware/rateLimiter");
const router = express.Router();

const AGENT_URL = process.env.AGENT_SERVICE_URL || "http://agent:8002";
const agent = axios.create({ baseURL: AGENT_URL, timeout: 300000 });

router.post("/chat", chatLimiter, async (req, res, next) => {
  try {
    const { data } = await agent.post("/chat", req.body);
    res.json(data);
  } catch (err) {
    next(err);
  }
});

router.get("/conversations", async (req, res, next) => {
  try {
    const { data } = await agent.get("/conversations", { params: req.query });
    res.json(data);
  } catch (err) {
    next(err);
  }
});

router.get("/conversations/:id", async (req, res, next) => {
  try {
    const { data } = await agent.get(`/conversations/${req.params.id}`);
    res.json(data);
  } catch (err) {
    next(err);
  }
});

router.delete("/conversations/:id", async (req, res, next) => {
  try {
    const { data } = await agent.delete(`/conversations/${req.params.id}`);
    res.json(data);
  } catch (err) {
    next(err);
  }
});

router.get("/suggested-queries", async (req, res, next) => {
  try {
    const { data } = await agent.get("/suggested-queries");
    res.json(data);
  } catch (err) {
    next(err);
  }
});

module.exports = router;
