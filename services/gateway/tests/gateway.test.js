const request = require("supertest");
const app = require("../src/index");

describe("Gateway Health", () => {
  it("GET /health returns ok", async () => {
    const res = await request(app).get("/health");
    expect(res.statusCode).toBe(200);
    expect(res.body.status).toBe("ok");
    expect(res.body.service).toBe("gateway");
  });

  it("GET / returns API info", async () => {
    const res = await request(app).get("/");
    expect(res.statusCode).toBe(200);
    expect(res.body.name).toMatch(/TrialMind/i);
  });

  it("Unknown route returns 404", async () => {
    const res = await request(app).get("/nonexistent-path");
    expect(res.statusCode).toBe(404);
  });
});
