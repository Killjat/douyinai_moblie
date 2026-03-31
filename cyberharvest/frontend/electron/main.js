const { app, BrowserWindow, ipcMain } = require("electron");
const { spawn } = require("child_process");
const path = require("path");

let mainWindow;
let backendProcess;

const BACKEND_PORT = 18765;
const isDev = process.env.NODE_ENV === "development";

function startBackend() {
  const scriptPath = path.join(__dirname, "../../backend/main.py");
  backendProcess = spawn("python3", [
    "-m", "uvicorn",
    "cyberharvest.backend.main:app",
    "--host", "127.0.0.1",
    "--port", String(BACKEND_PORT),
    "--reload"
  ], {
    cwd: path.join(__dirname, "../../.."),
    env: { ...process.env }
  });

  backendProcess.stdout.on("data", d => console.log("[backend]", d.toString()));
  backendProcess.stderr.on("data", d => console.error("[backend]", d.toString()));
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    titleBarStyle: "hiddenInset",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
    },
  });

  const url = isDev
    ? "http://localhost:5173"
    : `file://${path.join(__dirname, "../dist/index.html")}`;

  // 等后端启动
  setTimeout(() => mainWindow.loadURL(url), 2000);
}

app.whenReady().then(() => {
  startBackend();
  createWindow();
});

app.on("window-all-closed", () => {
  if (backendProcess) backendProcess.kill();
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

ipcMain.handle("get-backend-url", () => `http://127.0.0.1:${BACKEND_PORT}`);
