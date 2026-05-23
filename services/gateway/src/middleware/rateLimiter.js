const rateLimit = require("express-rate-limit");

const defaultLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 120,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "Too many requests, please try again later." },
});

const chatLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 30,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "Chat rate limit exceeded. Please wait before sending more messages." },
});

module.exports = { defaultLimiter, chatLimiter };
