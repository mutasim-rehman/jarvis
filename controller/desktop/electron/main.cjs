const path = require("node:path");
const fs = require("node:fs/promises");
const { spawn } = require("node:child_process");
const { app, BrowserWindow, ipcMain } = require("electron");

const repoRoot = path.resolve(__dirname, "..", "..", "..");
const maxLogLines = 300;

/** @type {Record<string, {id: string, name: string, command: string, args: string[], env: Record<string, string>, healthUrl?: string}>} */
const serviceConfigs = {
  backend: {
    id: "backend",
    name: "Backend API",
    command: "py",
    args: ["-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000"],
    env: {
      PYTHONPATH: repoRoot,
    },
    healthUrl: "http://127.0.0.1:8000/health",
  },
  executor: {
    id: "executor",
    name: "Executor API",
    command: "py",
    args: ["-m", "uvicorn", "executor.app.main:app", "--host", "127.0.0.1", "--port", "8001"],
    env: {
      PYTHONPATH: repoRoot,
    },
    healthUrl: "http://127.0.0.1:8001/health",
  },
  cli: {
    id: "cli",
    name: "Backend CLI",
    command: "py",
    args: ["backend/cli.py"],
    env: {
      PYTHONPATH: repoRoot,
    },
  },
};

/** @type {Map<string, {child: import("node:child_process").ChildProcess, startedAt: number}>} */
const runningProcesses = new Map();
/** @type {Map<string, string[]>} */
const serviceLogs = new Map();

function appendLog(serviceId, line) {
  if (!serviceLogs.has(serviceId)) {
    serviceLogs.set(serviceId, []);
  }
  const logs = serviceLogs.get(serviceId);
  if (!logs) {
    return;
  }
  logs.push(line);
  if (logs.length > maxLogLines) {
    logs.splice(0, logs.length - maxLogLines);
  }
  for (const win of BrowserWindow.getAllWindows()) {
    if (!win.isDestroyed()) {
      win.webContents.send("services:log", { serviceId, line });
    }
  }
}

function commandText(config) {
  return `${config.command} ${config.args.join(" ")}`;
}

function serviceStatus(serviceId) {
  const config = serviceConfigs[serviceId];
  const processEntry = runningProcesses.get(serviceId);
  const isRunning = !!(processEntry && !processEntry.child.killed);
  return {
    id: config.id,
    name: config.name,
    command: commandText(config),
    running: isRunning,
    pid: isRunning ? processEntry.child.pid ?? null : null,
    startedAt: isRunning ? processEntry.startedAt : null,
    logs: serviceLogs.get(serviceId) ?? [],
  };
}

function listServiceStatuses() {
  return Object.keys(serviceConfigs).map((serviceId) => serviceStatus(serviceId));
}

function wireProcessLogs(serviceId, child) {
  child.stdout?.on("data", (chunk) => {
    const lines = String(chunk).split(/\r?\n/).filter(Boolean);
    for (const line of lines) {
      appendLog(serviceId, line);
    }
  });

  child.stderr?.on("data", (chunk) => {
    const lines = String(chunk).split(/\r?\n/).filter(Boolean);
    for (const line of lines) {
      appendLog(serviceId, `[stderr] ${line}`);
    }
  });

  child.on("error", (error) => {
    appendLog(serviceId, `[error] ${error.message}`);
  });

  child.on("exit", (code, signal) => {
    appendLog(serviceId, `[exit] code=${code ?? "null"} signal=${signal ?? "null"}`);
    const current = runningProcesses.get(serviceId);
    if (current && current.child.pid === child.pid) {
      runningProcesses.delete(serviceId);
    }
  });
}

function startService(serviceId) {
  const config = serviceConfigs[serviceId];
  const current = runningProcesses.get(serviceId);
  if (current && !current.child.killed) {
    return serviceStatus(serviceId);
  }

  const child = spawn(config.command, config.args, {
    cwd: repoRoot,
    env: {
      ...process.env,
      ...config.env,
    },
    windowsHide: true,
  });
  runningProcesses.set(serviceId, { child, startedAt: Date.now() });
  appendLog(serviceId, `[start] ${commandText(config)}`);
  wireProcessLogs(serviceId, child);

  return serviceStatus(serviceId);
}

function stopService(serviceId) {
  const current = runningProcesses.get(serviceId);
  if (!current || current.child.killed) {
    return serviceStatus(serviceId);
  }

  appendLog(serviceId, "[stop] termination requested");
  current.child.kill();
  setTimeout(() => {
    const latest = runningProcesses.get(serviceId);
    if (latest && !latest.child.killed) {
      appendLog(serviceId, "[stop] force kill");
      latest.child.kill("SIGKILL");
    }
  }, 3000);

  return serviceStatus(serviceId);
}

async function checkHealth(serviceId) {
  const config = serviceConfigs[serviceId];
  if (!config?.healthUrl) {
    return { ok: false, status: 0, error: "No health endpoint configured." };
  }

  try {
    const response = await fetch(config.healthUrl, {
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) {
      return { ok: false, status: response.status, error: response.statusText };
    }
    const data = await response.json();
    return { ok: true, status: response.status, data };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return { ok: false, status: 0, error: message };
  }
}

async function callInteract(text, baseUrl) {
  const url = `${baseUrl.replace(/\/+$/, "")}/api/interact`;
  let response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ text }),
      signal: AbortSignal.timeout(60000),
    });
  } catch (error) {
    if (error instanceof Error && error.name === "TimeoutError") {
      throw new Error("Request timed out after 60s. Backend may still be processing.");
    }
    throw error;
  }

  if (!response.ok) {
    const responseText = await response.text();
    throw new Error(`Backend returned ${response.status}: ${responseText || response.statusText}`);
  }

  return response.json();
}

async function callTranscribe(wavBytesBase64, baseUrl) {
  const url = `${baseUrl.replace(/\/+$/, "")}/api/transcribe`;
  const wavBuffer = Buffer.from(wavBytesBase64, "base64");
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "audio/wav",
    },
    body: wavBuffer,
    signal: AbortSignal.timeout(45000),
  });

  if (!response.ok) {
    const responseText = await response.text();
    throw new Error(`Transcription failed ${response.status}: ${responseText || response.statusText}`);
  }

  return response.json();
}

async function callTts(text, baseUrl) {
  const url = `${baseUrl.replace(/\/+$/, "")}/api/tts`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text }),
    signal: AbortSignal.timeout(60000),
  });

  if (!response.ok) {
    const responseText = await response.text();
    throw new Error(`TTS failed ${response.status}: ${responseText || response.statusText}`);
  }

  return response.json();
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1300,
    height: 850,
    minWidth: 1080,
    minHeight: 720,
    backgroundColor: "#0e1015",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (!app.isPackaged) {
    win.loadURL("http://127.0.0.1:5173");
    return;
  }

  win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
}

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  for (const [serviceId] of runningProcesses) {
    stopService(serviceId);
  }
});

ipcMain.handle("services:list", async () => listServiceStatuses());
ipcMain.handle("services:start", async (_event, serviceId) => startService(serviceId));
ipcMain.handle("services:stop", async (_event, serviceId) => stopService(serviceId));
ipcMain.handle("services:start-all", async () => {
  for (const serviceId of Object.keys(serviceConfigs)) {
    startService(serviceId);
  }
  return listServiceStatuses();
});
ipcMain.handle("services:stop-all", async () => {
  for (const serviceId of Object.keys(serviceConfigs)) {
    stopService(serviceId);
  }
  return listServiceStatuses();
});
ipcMain.handle("services:health", async (_event, serviceId) => checkHealth(serviceId));
ipcMain.handle("backend:interact", async (_event, text, baseUrl) => {
  try {
    const data = await callInteract(text, baseUrl);
    return { ok: true, data };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    appendLog("backend", `[interact-error] ${message}`);
    return { ok: false, error: message };
  }
});
ipcMain.handle("backend:transcribe", async (_event, wavBytesBase64, baseUrl) => {
  try {
    const data = await callTranscribe(wavBytesBase64, baseUrl);
    return { ok: true, data };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown transcription error";
    appendLog("backend", `[transcribe-error] ${message}`);
    return { ok: false, error: message };
  }
});
ipcMain.handle("backend:tts", async (_event, text, baseUrl) => {
  try {
    const data = await callTts(text, baseUrl);
    return { ok: true, data };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown TTS error";
    appendLog("backend", `[tts-error] ${message}`);
    return { ok: false, error: message };
  }
});
ipcMain.handle("system:repo-root", async () => repoRoot);
ipcMain.handle("system:jarvis-profile", async () => {
  const profilePath = path.join(repoRoot, "jarvis.json");
  try {
    const raw = await fs.readFile(profilePath, "utf-8");
    return { ok: true, data: JSON.parse(raw) };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to read jarvis profile";
    return { ok: false, error: message };
  }
});
