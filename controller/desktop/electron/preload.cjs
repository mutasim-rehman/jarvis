const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desktopApi", {
  listServices: () => ipcRenderer.invoke("services:list"),
  startService: (serviceId) => ipcRenderer.invoke("services:start", serviceId),
  stopService: (serviceId) => ipcRenderer.invoke("services:stop", serviceId),
  startAllServices: () => ipcRenderer.invoke("services:start-all"),
  stopAllServices: () => ipcRenderer.invoke("services:stop-all"),
  checkServiceHealth: (serviceId) => ipcRenderer.invoke("services:health", serviceId),
  getServiceBaseUrl: (serviceId) => ipcRenderer.invoke("services:base-url", serviceId),
  setAuthSession: (accessToken, deviceId) =>
    ipcRenderer.invoke("auth:set-session", accessToken, deviceId),
  authStorageGetItem: (key) => ipcRenderer.invoke("auth:storage-get", key),
  authStorageSetItem: (key, value) => ipcRenderer.invoke("auth:storage-set", key, value),
  authStorageRemoveItem: (key) => ipcRenderer.invoke("auth:storage-remove", key),
  startOAuthListener: () => ipcRenderer.invoke("auth:start-oauth-listener"),
  openExternalUrl: (url) => ipcRenderer.invoke("auth:open-external-url", url),
  openOAuthWindow: (oauthUrl) => ipcRenderer.invoke("auth:open-oauth-window", oauthUrl),
  onOAuthCallback: (callback) => {
    const listener = (_event, callbackUrl) => callback(callbackUrl);
    ipcRenderer.on("auth:oauth-callback", listener);
    return () => {
      ipcRenderer.removeListener("auth:oauth-callback", listener);
    };
  },
  fetchBackend: (options) => ipcRenderer.invoke("backend:fetch", options),
  interactWithBackend: (text, baseUrl, chatProvider, accessToken) =>
    ipcRenderer.invoke("backend:interact", text, baseUrl, chatProvider, accessToken),
  transcribeAudio: (wavBytes, baseUrl) => ipcRenderer.invoke("backend:transcribe", wavBytes, baseUrl),
  synthesizeSpeech: (text, baseUrl) => ipcRenderer.invoke("backend:tts", text, baseUrl),
  getVoiceprintStatus: (baseUrl) => ipcRenderer.invoke("backend:voiceprint-status", baseUrl),
  resetVoiceprint: (baseUrl) => ipcRenderer.invoke("backend:voiceprint-reset", baseUrl),
  enrollVoiceprintSample: (wavBytes, baseUrl) => ipcRenderer.invoke("backend:voiceprint-enroll", wavBytes, baseUrl),
  finalizeVoiceprint: (baseUrl) => ipcRenderer.invoke("backend:voiceprint-finalize", baseUrl),
  verifyVoiceprint: (wavBytes, baseUrl) => ipcRenderer.invoke("backend:voiceprint-verify", wavBytes, baseUrl),
  getRepoRoot: () => ipcRenderer.invoke("system:repo-root"),
  getJarvisProfile: () => ipcRenderer.invoke("system:jarvis-profile"),
  listTerminals: () => ipcRenderer.invoke("system:list-terminals"),
  onServiceLog: (callback) => {
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on("services:log", listener);
    return () => {
      ipcRenderer.removeListener("services:log", listener);
    };
  },
  openDevTools: () => ipcRenderer.invoke("window:open-devtools"),
});
