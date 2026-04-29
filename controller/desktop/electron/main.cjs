const path = require("node:path");
const fs = require("node:fs/promises");
const net = require("node:net");
const { spawn } = require("node:child_process");
const os = require("node:os");
const { app, BrowserWindow, ipcMain } = require("electron");

const repoRoot = path.resolve(__dirname, "..", "..", "..");
const cursorProjectsDir = path.join(os.homedir(), ".cursor", "projects");
const projectName = path.basename(repoRoot);
const maxLogLines = 300;
/** @type {BrowserWindow | null} */
let mainWindow = null;

// Some Windows machines intermittently show a black renderer with GPU acceleration.
app.disableHardwareAcceleration();

function sanitizePathSegment(value) {
  return String(value)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function uniqueValues(values) {
  return [...new Set(values.filter(Boolean))];
}

function buildCursorProjectCandidates() {
  const parsed = path.parse(repoRoot);
  const driveSlug = sanitizePathSegment(parsed.root.replace(/[:\\/]/g, ""));
  const baseSlug = sanitizePathSegment(projectName);
  return uniqueValues([
    projectName,
    baseSlug,
    `${driveSlug}-${projectName}`,
    `${driveSlug}-${baseSlug}`,
  ]);
}

async function resolveCursorTerminalsDir() {
  const candidates = buildCursorProjectCandidates().map((name) =>
    path.join(cursorProjectsDir, name, "terminals")
  );

  for (const dirPath of candidates) {
    try {
      const stat = await fs.stat(dirPath);
      if (stat.isDirectory()) {
        return dirPath;
      }
    } catch {
      // Keep checking candidates.
    }
  }

  // Fallback: scan folders and pick the first entry that has a terminals directory and resembles this repo name.
  const entries = await fs.readdir(cursorProjectsDir, { withFileTypes: true });
  const normalizedRepoName = sanitizePathSegment(projectName);
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const normalizedEntry = sanitizePathSegment(entry.name);
    if (!normalizedEntry.includes(normalizedRepoName)) continue;
    const maybeDir = path.join(cursorProjectsDir, entry.name, "terminals");
    try {
      const stat = await fs.stat(maybeDir);
      if (stat.isDirectory()) {
        return maybeDir;
      }
    } catch {
      // Continue searching.
    }
  }

  throw new Error(`Unable to locate Cursor terminals directory under ${cursorProjectsDir}`);
}

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
/** @type {Map<string, {args: string[], healthUrl?: string, baseUrl?: string}>} */
const serviceRuntime = new Map();

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

function parsePortFromArgs(args) {
  const portFlagIndex = args.findIndex((arg) => arg === "--port");
  if (portFlagIndex < 0 || portFlagIndex + 1 >= args.length) {
    return null;
  }
  const parsed = Number(args[portFlagIndex + 1]);
  return Number.isFinite(parsed) ? parsed : null;
}

function withPortArgs(args, port) {
  const nextArgs = [...args];
  const portFlagIndex = nextArgs.findIndex((arg) => arg === "--port");
  if (portFlagIndex >= 0 && portFlagIndex + 1 < nextArgs.length) {
    nextArgs[portFlagIndex + 1] = String(port);
    return nextArgs;
  }
  nextArgs.push("--port", String(port));
  return nextArgs;
}

function checkPortAvailable(port, host) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => {
      resolve(false);
    });
    server.once("listening", () => {
      server.close(() => resolve(true));
    });
    server.listen(port, host);
  });
}

async function findAvailablePort(preferredPort, host, maxOffset = 25) {
  for (let offset = 0; offset <= maxOffset; offset += 1) {
    const candidate = preferredPort + offset;
    const isAvailable = await checkPortAvailable(candidate, host);
    if (isAvailable) {
      return candidate;
    }
  }
  return null;
}

function parseTerminalMetadata(content) {
  const lines = content.split(/\r?\n/);
  const start = lines.findIndex((line) => line.trim() === "---");
  if (start < 0) return {};
  const end = lines.findIndex((line, idx) => idx > start && line.trim() === "---");
  if (end < 0) return {};

  /** @type {Record<string, string>} */
  const meta = {};
  for (let i = start + 1; i < end; i += 1) {
    const line = lines[i];
    const match = line.match(/^([^:]+):\s*(.*)$/);
    if (!match) continue;
    const key = match[1].trim();
    const rawValue = (match[2] ?? "").trim();

    if (rawValue === "|") {
      const block = [];
      let j = i + 1;
      while (j < end) {
        const blockLine = lines[j];
        if (blockLine.startsWith("  ")) {
          block.push(blockLine.slice(2));
          j += 1;
          continue;
        }
        if (blockLine.trim() === "") {
          block.push("");
          j += 1;
          continue;
        }
        break;
      }
      meta[key] = block.join("\n").trim();
      i = j - 1;
      continue;
    }

    meta[key] = rawValue;
  }

  return meta;
}

function serviceStatus(serviceId) {
  const config = serviceConfigs[serviceId];
  const runtime = serviceRuntime.get(serviceId);
  const processEntry = runningProcesses.get(serviceId);
  const isRunning = !!(processEntry && !processEntry.child.killed);
  const activeConfig = runtime ? { ...config, ...runtime } : config;
  return {
    id: config.id,
    name: config.name,
    command: commandText(activeConfig),
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

async function resolveRuntimeForService(serviceId) {
  const config = serviceConfigs[serviceId];
  const preferredPort = parsePortFromArgs(config.args);
  if (!preferredPort || !config.healthUrl) {
    const noPortRuntime = { args: [...config.args] };
    serviceRuntime.set(serviceId, noPortRuntime);
    return noPortRuntime;
  }

  const host = config.healthUrl.includes("127.0.0.1") ? "127.0.0.1" : "0.0.0.0";
  const selectedPort = await findAvailablePort(preferredPort, host);
  if (!selectedPort) {
    throw new Error(`${config.name}: unable to find available port near ${preferredPort}`);
  }

  const runtime = {
    args: withPortArgs(config.args, selectedPort),
    healthUrl: config.healthUrl.replace(/:\d+/, `:${selectedPort}`),
    baseUrl: `http://${host}:${selectedPort}`,
  };
  serviceRuntime.set(serviceId, runtime);
  if (selectedPort !== preferredPort) {
    appendLog(
      serviceId,
      `[port-fallback] preferred ${preferredPort} busy, using ${selectedPort}`
    );
  }
  return runtime;
}

async function startService(serviceId) {
  const config = serviceConfigs[serviceId];
  const current = runningProcesses.get(serviceId);
  if (current && !current.child.killed) {
    return serviceStatus(serviceId);
  }

  const runtime = await resolveRuntimeForService(serviceId);
  const child = spawn(config.command, runtime.args, {
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
  const runtime = serviceRuntime.get(serviceId);
  const healthUrl = runtime?.healthUrl ?? config?.healthUrl;
  if (!healthUrl) {
    return { ok: false, status: 0, error: "No health endpoint configured." };
  }

  try {
    const response = await fetch(healthUrl, {
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

async function callInteract(text, baseUrl, chatProvider) {
  const url = `${baseUrl.replace(/\/+$/, "")}/api/interact`;
  const startedAt = Date.now();
  let response;
  const body = { text };
  if (chatProvider) {
    body.chat_provider = chatProvider;
  }
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
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
  const data = await response.json();
  appendLog("backend", `[perf] interact_roundtrip_ms=${Date.now() - startedAt} chars=${text.length}`);
  return data;
}

async function callTranscribe(wavBytes, baseUrl) {
  const url = `${baseUrl.replace(/\/+$/, "")}/api/transcribe`;
  const wavBuffer = Buffer.isBuffer(wavBytes) ? wavBytes : Buffer.from(wavBytes);
  const startedAt = Date.now();
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

  appendLog("backend", `[perf] transcribe_roundtrip_ms=${Date.now() - startedAt} payload_bytes=${wavBuffer.length}`);
  return response.json();
}

async function callTts(text, baseUrl) {
  const url = `${baseUrl.replace(/\/+$/, "")}/api/tts`;
  const startedAt = Date.now();
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
  const data = await response.json();
  appendLog("backend", `[perf] tts_roundtrip_ms=${Date.now() - startedAt} chars=${text.length}`);
  return data;
}

async function listCursorTerminals() {
  try {
    const cursorTerminalsDir = await resolveCursorTerminalsDir();
    const entries = await fs.readdir(cursorTerminalsDir, { withFileTypes: true });
    const terminalFiles = entries
      .filter((entry) => entry.isFile() && entry.name.endsWith(".txt"))
      .map((entry) => entry.name)
      .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));

    const terminals = await Promise.all(
      terminalFiles.map(async (filename) => {
        const terminalId = filename.replace(/\.txt$/i, "");
        const content = await fs.readFile(path.join(cursorTerminalsDir, filename), "utf-8");
        const meta = parseTerminalMetadata(content);

        return {
          id: terminalId,
          pid: Number(meta.pid) || null,
          cwd: meta.cwd || "",
          activeCommand: meta.active_command || "",
          lastCommand: meta.last_command || meta.active_command || "",
          lastExitCode: meta.last_exit_code ?? "",
        };
      })
    );

    return { ok: true, data: terminals };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to read terminals";
    return { ok: false, error: message, data: [] };
  }
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

  win.webContents.on("did-fail-load", (_event, errorCode, errorDescription, validatedUrl) => {
    // Dev server can race during startup; retry once after a short delay.
    if (!app.isPackaged && validatedUrl.includes("127.0.0.1:5173")) {
      console.warn(
        `[electron] did-fail-load code=${errorCode} reason=${errorDescription}. Retrying load...`
      );
      setTimeout(() => {
        if (!win.isDestroyed()) {
          win.loadURL("http://127.0.0.1:5173");
        }
      }, 900);
    }
  });

  if (!app.isPackaged) {
    win.loadURL("http://127.0.0.1:5173");
  } else {
    win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }

  mainWindow = win;
  win.on("closed", () => {
    if (mainWindow === win) {
      mainWindow = null;
    }
  });
}

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (!mainWindow || mainWindow.isDestroyed()) {
      createWindow();
      return;
    }
    mainWindow.focus();
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

function getServiceBaseUrl(serviceId) {
  const config = serviceConfigs[serviceId];
  const runtime = serviceRuntime.get(serviceId);
  if (runtime?.baseUrl) {
    return runtime.baseUrl;
  }
  const preferredPort = parsePortFromArgs(config.args);
  if (!preferredPort) {
    return "";
  }
  return `http://127.0.0.1:${preferredPort}`;
}

ipcMain.handle("services:list", async () => listServiceStatuses());
ipcMain.handle("services:start", async (_event, serviceId) => startService(serviceId));
ipcMain.handle("services:stop", async (_event, serviceId) => stopService(serviceId));
ipcMain.handle("services:start-all", async () => {
  for (const serviceId of Object.keys(serviceConfigs)) {
    // start each service in order so port fallback logs stay readable.
    await startService(serviceId);
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
ipcMain.handle("services:base-url", async (_event, serviceId) => getServiceBaseUrl(serviceId));
ipcMain.handle("backend:interact", async (_event, text, baseUrl, chatProvider) => {
  try {
    const data = await callInteract(text, baseUrl, chatProvider);
    return { ok: true, data };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    appendLog("backend", `[interact-error] ${message}`);
    return { ok: false, error: message };
  }
});
ipcMain.handle("backend:transcribe", async (_event, wavBytes, baseUrl) => {
  try {
    const data = await callTranscribe(wavBytes, baseUrl);
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
ipcMain.handle("system:list-terminals", async () => listCursorTerminals());
ipcMain.handle("window:open-devtools", async (event) => {
  try {
    const senderWindow = BrowserWindow.fromWebContents(event.sender);
    if (!senderWindow || senderWindow.isDestroyed()) {
      return { ok: false, error: "Window not available" };
    }
    senderWindow.webContents.openDevTools({ mode: "detach" });
    return { ok: true };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to open DevTools";
    return { ok: false, error: message };
  }
});
