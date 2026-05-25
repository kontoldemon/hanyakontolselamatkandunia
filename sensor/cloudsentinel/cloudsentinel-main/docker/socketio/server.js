import cors from "cors";
import express from "express";
import http from "node:http";
import { Server } from "socket.io";

const port = Number.parseInt(process.env.PORT || "3001", 10);
const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  }
});

app.use(cors());
app.use(express.json({ limit: "1mb" }));

app.get("/health", (_req, res) => {
  res.json({ ok: true, service: "cloudsentinel-socketio-bridge" });
});

app.post("/events", (req, res) => {
  const event = req.body;
  io.emit("cloudsentinel:event", event);
  res.status(202).json({ accepted: true });
});

io.on("connection", (socket) => {
  socket.emit("cloudsentinel:hello", {
    service: "cloudsentinel-socketio-bridge"
  });
});

server.listen(port, "0.0.0.0", () => {
  console.log(`CloudSentinel Socket.io bridge listening on ${port}`);
});
