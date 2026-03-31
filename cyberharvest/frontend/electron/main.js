const { app, BrowserWindow, ipcMain } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const net = require("net");

let mainWindow;
let backendProcess;

const BACKEND_PORT = 18765;
const isDev = process.env.NODE_ENV === "development";

function getBackendExecutable() {
  if (isDev) {
    // 开发模式：用 python3
    return {
      cmd: "python3",
      args: ["-m", "uvicorn", "cyberharvest.backend.main:app",
             "--host", "127.0.0.1", "--port", String(BACKEND_PORT), "--reload"],
      cwd: path.join(__dirname, "../../.."),
    };
  }
  // 打包模式：用 PyInstaller 打出的可执行文件
  const exeName = process.platform === "win32"
    ? "cyberharvest-server.exe"
    : "cyberharvest-server";
  const exePath = path.join(process.resourcesPath, exeName);
  return {
    cmd: exePath,
    args: [String(BACKEND_PORT)],
    cwd: path.dirname(exePath),
  };
}

function startBackend() {
  const { cmd, args, cwd } = getBackendExecutable();
  console.log("[backend] starting:", cmd, args.join(" "));
  backendProcess = spawn(cmd, args, { cwd, env: { ...process.env } });
  backendProcess.stdout.on("data", d => console.log("[backend]", d.toString().trim()));
  backendProcess.stderr.on("data", d => console.error("[backend]", d.toString().trim()));
  backendProcess.on("exit", code => console.log("[backend] exited:", code));
}

function waitForBackend(retries = 20) {
  return new Promise((resolve, reject) => {
    const check = (n) => {
      const sock = net.connect(BACKEND_PORT, "127.0.0.1", () => {
        sock.destroy(); resolve();
      });
      sock.on("error", () => {
        if (n <= 0) return reject(new Error("backend timeout"));
        setTimeout(() => check(n - 1), 500);
      });
    };
    check(retries);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 960,
    minHeight: 640,
    titleBarStyle: "hiddenInset",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
    },
  });

  const url = isDev
    ? "http://localhost:5173"
    : `file://${path.join(__dirname, "../dist/index.html")}`;

  mainWindow.loadURL(url);
}

app.whenReady().then(async () => {
  startBackend();
  try {
    await waitForBackend();
    console.log("[backend] ready");
  } catch (e) {
    console.error("[backend] failed to start:", e.message);
  }
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
