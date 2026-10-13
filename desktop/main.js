/**
 * CAI Desktop — Electron host for the Python web sidecar.
 *
 * Opens immediately (Harness-like). Workspace is chosen inside the app.
 */
const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const http = require("http");
const net = require("net");
const path = require("path");
const os = require("os");

const PREFS_PATH = path.join(app.getPath("userData"), "desktop-prefs.json");
const REPO_ROOT = path.resolve(__dirname, "..");

let mainWindow = null;
let sidecar = null;
let sidecarPort = 0;

function loadPrefs() {
  try {
    return JSON.parse(fs.readFileSync(PREFS_PATH, "utf8"));
  } catch {
    return { recentWorkspaces: [] };
  }
}

function savePrefs(prefs) {
  fs.mkdirSync(path.dirname(PREFS_PATH), { recursive: true });
  fs.writeFileSync(PREFS_PATH, JSON.stringify(prefs, null, 2), "utf8");
}

function rememberWorkspace(ws) {
  if (!ws) return loadPrefs();
  const prefs = loadPrefs();
  prefs.workspace = ws;
  const recent = (prefs.recentWorkspaces || []).filter((p) => p !== ws);
  recent.unshift(ws);
  prefs.recentWorkspaces = recent.slice(0, 12);
  savePrefs(prefs);
  return prefs;
}

function defaultWorkspace() {
  const prefs = loadPrefs();
  if (prefs.workspace && fs.existsSync(prefs.workspace)) return prefs.workspace;
  for (const p of prefs.recentWorkspaces || []) {
    if (p && fs.existsSync(p)) return p;
  }
  // Harness-like: boot into a sensible default, add more workspaces in-app
  const home = os.homedir();
  return fs.existsSync(home) ? home : REPO_ROOT;
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
    srv.on("error", reject);
  });
}

function waitForReady(port, timeoutMs = 45000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get({ host: "127.0.0.1", port, path: "/api/info", timeout: 1500 }, (res) => {
        res.resume();
        if (res.statusCode === 200) resolve();
        else if (Date.now() - started > timeoutMs) reject(new Error("sidecar timeout"));
        else setTimeout(tick, 300);
      });
      req.on("error", () => {
        if (Date.now() - started > timeoutMs) reject(new Error("sidecar timeout"));
        else setTimeout(tick, 300);
      });
    };
    tick();
  });
}

function pythonCmd() {
  if (process.env.CAI_PYTHON) return process.env.CAI_PYTHON;
  return process.platform === "win32" ? "python" : "python3";
}

async function startSidecar(workspace) {
  sidecarPort = await findFreePort();
  const env = {
    ...process.env,
    CAI_WORKSPACE: workspace,
    CAI_HOME: process.env.CAI_HOME || path.join(os.homedir(), ".cai"),
    PYTHONPATH: path.join(REPO_ROOT, "src") + path.delimiter + (process.env.PYTHONPATH || ""),
  };
  const args = ["-m", "cai_agent", "web", "--host", "127.0.0.1", "--port", String(sidecarPort)];
  sidecar = spawn(pythonCmd(), args, {
    cwd: REPO_ROOT,
    env,
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  sidecar.stdout.on("data", (d) => console.log(`[sidecar] ${d}`));
  sidecar.stderr.on("data", (d) => console.error(`[sidecar] ${d}`));
  sidecar.on("exit", (code) => {
    console.log(`sidecar exited: ${code}`);
    sidecar = null;
  });
  await waitForReady(sidecarPort);
  return sidecarPort;
}

function stopSidecar() {
  if (!sidecar) return;
  try {
    if (process.platform === "win32") {
      spawn("taskkill", ["/pid", String(sidecar.pid), "/f", "/t"]);
    } else {
      sidecar.kill("SIGTERM");
    }
  } catch (_) {}
  sidecar = null;
}

async function createWindow() {
  const workspace = defaultWorkspace();
  rememberWorkspace(workspace);
  try {
    await startSidecar(workspace);
  } catch (err) {
    dialog.showErrorBox(
      "CAI sidecar failed",
      `${err.message}\n\nEnsure Python deps are installed:\n  pip install -e ".[dev]"\nin ${REPO_ROOT}`,
    );
    app.quit();
    return;
  }

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 960,
    minHeight: 640,
    title: "CAI Agent",
    backgroundColor: "#0c0e12",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow.loadURL(`http://127.0.0.1:${sidecarPort}/`);
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

ipcMain.handle("desktop:get-prefs", () => loadPrefs());
ipcMain.handle("desktop:set-workspace", (_e, ws) => rememberWorkspace(ws));
ipcMain.handle("desktop:pick-workspace", async () => {
  const result = await dialog.showOpenDialog(mainWindow || undefined, {
    title: "添加工作区",
    properties: ["openDirectory", "createDirectory"],
  });
  if (result.canceled || !result.filePaths[0]) return null;
  return rememberWorkspace(result.filePaths[0]).workspace;
});
ipcMain.handle("desktop:list-workspaces", () => {
  const prefs = loadPrefs();
  const cur = prefs.workspace;
  const recent = prefs.recentWorkspaces || [];
  return { current: cur, recent };
});

app.whenReady().then(createWindow);
app.on("window-all-closed", () => {
  stopSidecar();
  if (process.platform !== "darwin") app.quit();
});
app.on("before-quit", () => stopSidecar());
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
