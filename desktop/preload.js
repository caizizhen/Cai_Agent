const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("caiDesktop", {
  isDesktop: true,
  pickWorkspace: () => ipcRenderer.invoke("desktop:pick-workspace"),
  getPrefs: () => ipcRenderer.invoke("desktop:get-prefs"),
  setWorkspace: (path) => ipcRenderer.invoke("desktop:set-workspace", path),
  listWorkspaces: () => ipcRenderer.invoke("desktop:list-workspaces"),
});
