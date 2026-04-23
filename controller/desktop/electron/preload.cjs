const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desktopApi", {
  listServices: () => ipcRenderer.invoke("services:list"),
  startService: (serviceId) => ipcRenderer.invoke("services:start", serviceId),
  stopService: (serviceId) => ipcRenderer.invoke("services:stop", serviceId),
  startAllServices: () => ipcRenderer.invoke("services:start-all"),
  stopAllServices: () => ipcRenderer.invoke("services:stop-all"),
  checkServiceHealth: (serviceId) => ipcRenderer.invoke("services:health", serviceId),
  interactWithBackend: (text, baseUrl) => ipcRenderer.invoke("backend:interact", text, baseUrl),
  transcribeAudio: (wavBytesBase64, baseUrl) => ipcRenderer.invoke("backend:transcribe", wavBytesBase64, baseUrl),
  synthesizeSpeech: (text, baseUrl) => ipcRenderer.invoke("backend:tts", text, baseUrl),
  getRepoRoot: () => ipcRenderer.invoke("system:repo-root"),
  getJarvisProfile: () => ipcRenderer.invoke("system:jarvis-profile"),
  onServiceLog: (callback) => {
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on("services:log", listener);
    return () => {
      ipcRenderer.removeListener("services:log", listener);
    };
  },
});
