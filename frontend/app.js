const express = require("express");
const axios = require("axios");
const path = require("path");
const app = express();

const API_HOST = process.env.API_HOST;
const API_PORT = process.env.API_PORT;
const PORT = parseInt(process.env.FRONTEND_PORT);
const REQUEST_TIMEOUT_MS = parseInt(process.env.REQUEST_TIMEOUT_MS);

const API_URL = API_HOST + ":" + API_PORT;
app.use(express.json());
app.use(express.static(path.join(__dirname, "views")));

app.get("/health", (req, res) => res.json({ status: "ok" }));

app.post("/submit", async (req, res) => {
  try {
    const response = await axios.post(
      `${API_URL}/jobs`,
      {},
      { timeout: REQUEST_TIMEOUT_MS },
    );
    res.status(201).json(response.data);
  } catch (err) {
    console.error("[POST /submit]", err.message);
    res.status(500).json({ error: "something went wrong" });
  }
});

app.get("/status/:id", async (req, res) => {
  try {
    const response = await axios.get(`${API_URL}/jobs/${req.params.id}`, {
      timeout: REQUEST_TIMEOUT_MS,
    });
    res.json(response.data);
  } catch (err) {
    console.error("[GET /status]", err.message);
    const statusCode = err.response?.status === 404 ? 404 : 500;
    const message =
      err.response?.status === 404
        ? "No job found for the given id"
        : "something went wrong";

    res.status(statusCode).json({ error: message });
  }
});

app.listen(PORT, () => {
  console.log("Frontend running on port " + PORT);
});
