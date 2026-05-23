const express = require("express");
const axios = require("axios");
const router = express.Router();

const ML_URL = process.env.ML_SERVICE_URL || "http://ml:8001";

// Forward to ML service
const ml = axios.create({ baseURL: ML_URL, timeout: 30000 });

router.get("/predict/:nctId", async (req, res, next) => {
  try {
    const { data } = await ml.get(`/predict/${req.params.nctId}`);
    res.json(data);
  } catch (err) {
    next(err);
  }
});

router.post("/predict", async (req, res, next) => {
  try {
    const { data } = await ml.post("/predict", req.body);
    res.json(data);
  } catch (err) {
    next(err);
  }
});

router.get("/benchmark", async (req, res, next) => {
  try {
    const { data } = await ml.get("/benchmark", { params: req.query });
    res.json(data);
  } catch (err) {
    next(err);
  }
});

router.get("/benchmark/by-phase", async (req, res, next) => {
  try {
    const { data } = await ml.get("/benchmark/by-phase");
    res.json(data);
  } catch (err) {
    next(err);
  }
});

router.get("/benchmark/by-area", async (req, res, next) => {
  try {
    const { data } = await ml.get("/benchmark/by-therapeutic-area");
    res.json(data);
  } catch (err) {
    next(err);
  }
});

router.get("/model/info", async (req, res, next) => {
  try {
    const { data } = await ml.get("/model/info");
    res.json(data);
  } catch (err) {
    next(err);
  }
});

module.exports = router;
