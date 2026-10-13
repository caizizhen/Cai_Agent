/* CAI — Pi core + DeepSeek Harness–style sidebar */
(() => {
  const $ = (id) => document.getElementById(id);
  const els = {
    tree: $("workspace-tree"),
    chatInner: $("chat-inner"),
    hero: $("hero"),
    input: $("input"),
    send: $("send"),
    statusDot: $("status-dot"),
    headerTitle: $("header-title"),
    headerModel: $("header-model"),
    wsChip: $("ws-chip"),
    hint: $("composer-hint"),
    chat: $("chat"),
    fileTree: $("file-tree"),
  };

  let sessionId = localStorage.getItem("cai_session") || "";
  let turnActive = false;
  let streamEl = null;
  let sawStream = false;
  let runStarted = 0;
  let tickTimer = null;
  let settings = { theme: "dark" };
  let runtime = {};
  let openFilePath = "";
  let fileDirty = false;
  let thinkingEl = null;
  let workspacePaths = [];
  let currentWorkspace = "";
  let allSessions = [];
  let wsQuery = "";
  let filterHasSessions = localStorage.getItem("cai_ws_filter") === "1";
  let expanded = new Set(JSON.parse(localStorage.getItem("cai_ws_expanded") || "[]"));
  const desktop = window.caiDesktop || null;

  const FOLDER_SVG =
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/></svg>';

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  const KW = {
    py: /\b(and|as|assert|async|await|break|class|continue|def|del|elif|else|except|False|finally|for|from|global|if|import|in|is|lambda|None|nonlocal|not|or|pass|raise|return|True|try|while|with|yield)\b/g,
    js: /\b(async|await|break|case|catch|class|const|continue|default|else|export|extends|false|finally|for|function|if|import|let|new|null|return|true|try|typeof|undefined|var|while)\b/g,
    sh: /\b(if|then|else|elif|fi|for|while|do|done|case|esac|in|function|return|export|true|false)\b/g,
  };

  function highlightCode(escaped, lang) {
    let s = escaped;
    const L = (lang || "").toLowerCase();
    if (L === "py" || L === "python" || L === "sh" || L === "bash") {
      s = s.replace(/(^|\n)(\s*#.*)/g, "$1<span class=\"tok-cm\">$2</span>");
    }
    if (L === "js" || L === "javascript") {
      s = s.replace(/(\/\/[^\n]*)/g, "<span class=\"tok-cm\">$1</span>");
    }
    s = s.replace(/("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')/g, (m) =>
      m.includes("tok-") ? m : `<span class="tok-str">${m}</span>`,
    );
    s = s.replace(/\b(\d+\.?\d*)\b/g, '<span class="tok-num">$1</span>');
    const key = L === "python" || L === "py" ? "py" : L === "javascript" || L === "js" ? "js" : L === "bash" || L === "sh" ? "sh" : null;
    if (key && KW[key]) s = s.replace(KW[key], '<span class="tok-kw">$1</span>');
    return s;
  }

  function renderMd(text) {
    const raw = String(text ?? "");
    const blocks = [];
    const marked = raw.replace(/```(\w+)?\n?([\s\S]*?)```/g, (_, lang, code) => {
      const label = lang ? `<div class="code-lang">${esc(lang)}</div>` : "";
      const body = highlightCode(esc(code.replace(/\n$/, "")), lang || "");
      const i = blocks.length;
      blocks.push(`${label}<pre class="md-code"><code>${body}</code></pre>`);
      return `\u0000B${i}\u0000`;
    });
    let s = esc(marked);
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/^### (.+)$/gm, "<h4>$1</h4>");
    s = s.replace(/^## (.+)$/gm, "<h3>$1</h3>");
    s = s.replace(/^\* (.+)$/gm, "<li>$1</li>");
    s = s.replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`);
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    s = s.replace(/\n/g, "<br/>");
    s = s.replace(/\u0000B(\d+)\u0000/g, (_, i) => blocks[Number(i)] || "");
    return s;
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme === "light" ? "light" : "dark");
    settings.theme = theme === "light" ? "light" : "dark";
  }

  function setRunning(on) {
    turnActive = on;
    els.statusDot.classList.toggle("running", on);
    els.statusDot.title = on ? "running" : "idle";
    els.send.disabled = on;
    if (on) {
      runStarted = Date.now();
      els.hint.textContent = "Working…";
      clearInterval(tickTimer);
      tickTimer = setInterval(() => {
        const s = Math.floor((Date.now() - runStarted) / 1000);
        els.hint.textContent = `Working… ${s}s`;
      }, 400);
    } else {
      clearInterval(tickTimer);
      els.hint.textContent = "Ready";
    }
  }

  function showHero(show) {
    if (els.hero) els.hero.style.display = show ? "flex" : "none";
  }

  function clearChatKeepHero() {
    [...els.chatInner.querySelectorAll(".msg, .tool-card, .meta-line")].forEach((n) => n.remove());
    showHero(true);
  }

  function appendNode(node) {
    showHero(false);
    els.chatInner.appendChild(node);
    els.chat.scrollTop = els.chat.scrollHeight;
    return node;
  }

  function addUser(text) {
    const d = document.createElement("div");
    d.className = "msg msg-user";
    d.innerHTML = `<div class="bubble">${esc(text)}</div>`;
    appendNode(d);
  }

  function addAssistant(text) {
    const d = document.createElement("div");
    d.className = "msg msg-assistant";
    d.innerHTML = `<div class="label">CAI</div><div class="body">${renderMd(text)}</div>`;
    appendNode(d);
    return d;
  }

  function ensureStream() {
    if (!streamEl) {
      streamEl = addAssistant("");
      sawStream = false;
    }
    return streamEl.querySelector(".body");
  }

  function addMeta(text) {
    const d = document.createElement("div");
    d.className = "meta-line";
    d.textContent = text;
    appendNode(d);
  }

  function addToolCard(name, summary, result) {
    const d = document.createElement("details");
    d.className = "tool-card";
    d.open = false;
    d.innerHTML = `<summary><span class="tool-name">${esc(name)}</span><span class="tool-sum">${esc(summary || "")}</span></summary><pre>${esc(result || summary || "")}</pre>`;
    appendNode(d);
  }

  function ensureThinking() {
    if (!thinkingEl) {
      thinkingEl = document.createElement("details");
      thinkingEl.className = "thinking-card";
      thinkingEl.open = false;
      thinkingEl.innerHTML = `<summary>Thinking</summary><pre></pre>`;
      appendNode(thinkingEl);
    }
    return thinkingEl.querySelector("pre");
  }

  function fillSettingsForm(rt) {
    runtime = rt || {};
    $("set-provider").value = runtime.provider === "anthropic" ? "anthropic" : "openai";
    $("set-base-url").value = runtime.base_url || "";
    $("set-model").value = runtime.model || "";
    $("set-api-key").value = "";
    $("set-api-key").placeholder = runtime.api_key_set ? "•••••••• (leave blank to keep)" : "api key";
    $("set-max-steps").value = String(runtime.max_steps || 16);
    $("set-approval").value = runtime.approval || "auto";
    $("set-stream").checked = runtime.stream !== false;
    $("set-debug").checked = !!runtime.debug;
    $("set-theme").value = runtime.theme || settings.theme || "dark";
    $("set-workspace-label").textContent = runtime.workspace || "—";
    const sel = $("set-model-select");
    if (sel && runtime.model) {
      let found = false;
      [...sel.options].forEach((o) => {
        if (o.value === runtime.model) found = true;
      });
      if (!found) {
        const opt = document.createElement("option");
        opt.value = runtime.model;
        opt.textContent = runtime.model;
        sel.appendChild(opt);
      }
      sel.value = runtime.model;
    }
  }

  function populateModelSelect(models, selected) {
    const sel = $("set-model-select");
    sel.innerHTML = '<option value="">— 选择模型 —</option>';
    (models || []).forEach((m) => {
      const id = typeof m === "string" ? m : m.id;
      const name = typeof m === "string" ? m : m.name || m.id;
      const opt = document.createElement("option");
      opt.value = id;
      opt.textContent = name;
      sel.appendChild(opt);
    });
    if (selected) {
      sel.value = selected;
      $("set-model").value = selected;
    }
  }

  function normPath(p) {
    return String(p || "").replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase();
  }

  function folderName(p) {
    const parts = String(p || "").replace(/\\/g, "/").split("/").filter(Boolean);
    return parts[parts.length - 1] || p || "workspace";
  }

  function setWsChip(path) {
    const label = path ? folderName(path) : "—";
    els.wsChip.textContent = label;
    els.wsChip.title = path || "当前工作区";
  }

  function persistExpanded() {
    localStorage.setItem("cai_ws_expanded", JSON.stringify([...expanded]));
  }

  function relativeTime(iso) {
    if (!iso) return "";
    const t = Date.parse(iso);
    if (!Number.isFinite(t)) return "";
    const sec = Math.max(0, Math.floor((Date.now() - t) / 1000));
    if (sec < 60) return "刚刚";
    if (sec < 3600) return Math.floor(sec / 60) + "分钟";
    if (sec < 86400) return Math.floor(sec / 3600) + "小时";
    if (sec < 86400 * 30) return Math.floor(sec / 86400) + "天";
    return Math.floor(sec / (86400 * 30)) + "月";
  }

  async function syncDesktopRecents() {
    if (!desktop || !desktop.listWorkspaces) return;
    try {
      const pref = await desktop.listWorkspaces();
      const recent = pref.recent || [];
      for (const p of recent) {
        if (!p) continue;
        await fetch("/api/workspaces", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: p, activate: false }),
        });
      }
    } catch (_) {}
  }

  function matchQuery(text) {
    if (!wsQuery) return true;
    return String(text || "").toLowerCase().includes(wsQuery);
  }

  function sessionsForWorkspace(wsPath) {
    const key = normPath(wsPath);
    return allSessions.filter((s) => normPath(s.workspace) === key);
  }

  function ungroupedSessions() {
    const known = new Set(workspacePaths.map(normPath));
    return allSessions.filter((s) => !s.workspace || !known.has(normPath(s.workspace)));
  }

  function renderTree() {
    if (!els.tree) return;
    els.tree.innerHTML = "";
    const q = wsQuery.trim().toLowerCase();
    wsQuery = q;

    const groups = workspacePaths.map((p) => ({
      key: p,
      name: folderName(p),
      sessions: sessionsForWorkspace(p),
      isUngrouped: false,
    }));
    const ug = ungroupedSessions();
    groups.push({ key: "__ungrouped__", name: "未分组", sessions: ug, isUngrouped: true });

    let shown = 0;
    groups.forEach((g) => {
      const nameHit = matchQuery(g.name);
      const sess = g.sessions.filter((s) => nameHit || matchQuery(s.preview) || matchQuery(s.id));
      if (filterHasSessions && !sess.length && !g.isUngrouped) return;
      if (q && !nameHit && !sess.length) return;
      if (g.isUngrouped && !sess.length && !workspacePaths.length) {
        /* still show empty hint below */
      } else if (g.isUngrouped && !sess.length) {
        return;
      }

      const activeWs = !g.isUngrouped && normPath(g.key) === normPath(currentWorkspace);
      const isOpen = expanded.has(g.key) || (!!q && sess.length > 0) || activeWs;

      const folderBtn = document.createElement("button");
      folderBtn.type = "button";
      folderBtn.className = "ws-folder" + (activeWs ? " active" : "");
      folderBtn.title = g.isUngrouped ? "未绑定工作区的会话" : g.key;
      folderBtn.innerHTML =
        `<span class="fold-ico">${FOLDER_SVG}</span>` +
        `<span class="fold-name">${esc(g.name)}</span>`;
      folderBtn.onclick = async () => {
        if (expanded.has(g.key)) expanded.delete(g.key);
        else expanded.add(g.key);
        persistExpanded();
        if (!g.isUngrouped) await activateWorkspace(g.key, { quiet: true });
        else renderTree();
      };
      els.tree.appendChild(folderBtn);
      shown += 1;

      if (isOpen && sess.length) {
        const box = document.createElement("div");
        box.className = "ws-children";
        sess.forEach((s) => {
          const b = document.createElement("button");
          b.type = "button";
          b.className = "ws-session" + (s.id === sessionId ? " active" : "");
          b.innerHTML =
            `<span class="sess-title">${esc(s.preview || "新会话")}</span>` +
            `<span class="sess-time">${esc(relativeTime(s.updated_at))}</span>`;
          b.onclick = async () => {
            if (!g.isUngrouped && normPath(g.key) !== normPath(currentWorkspace)) {
              await activateWorkspace(g.key, { quiet: true });
            }
            await switchSession(s.id);
          };
          box.appendChild(b);
        });
        els.tree.appendChild(box);
      }
    });

    if (!workspacePaths.length && !allSessions.length) {
      els.tree.innerHTML = '<p class="hint ws-empty">还没有工作区。点击右上角「＋」添加项目文件夹。</p>';
    } else if (!shown) {
      els.tree.innerHTML = '<p class="hint ws-empty">没有匹配的工作区或会话。</p>';
    }

    setWsChip(currentWorkspace);
    $("btn-ws-filter")?.classList.toggle("active", filterHasSessions);
  }

  async function refreshSidebar() {
    const [wsData, sessData] = await Promise.all([
      fetch("/api/workspaces").then((r) => r.json()),
      fetch("/api/sessions").then((r) => r.json()),
    ]);
    workspacePaths = wsData.items || [];
    currentWorkspace = wsData.current || "";
    allSessions = sessData.sessions || [];
    if (currentWorkspace && !expanded.has(currentWorkspace)) {
      expanded.add(currentWorkspace);
      persistExpanded();
    }
    renderTree();
  }

  async function activateWorkspace(path, opts = {}) {
    const res = await fetch("/api/workspaces/activate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    }).then((r) => r.json());
    if (res.error) {
      addMeta(res.error);
      return;
    }
    if (desktop && desktop.setWorkspace) await desktop.setWorkspace(path);
    if (res.workspace) {
      fillSettingsForm(res);
      currentWorkspace = res.workspace;
      els.headerModel.textContent = res.model || els.headerModel.textContent;
    }
    expanded.add(path);
    persistExpanded();
    await refreshSidebar();
    if (!opts.quiet) addMeta("工作区 → " + folderName(path));
  }

  async function addWorkspace() {
    let path = null;
    if (desktop && desktop.pickWorkspace) {
      path = await desktop.pickWorkspace();
    } else {
      path = prompt("输入工作区绝对路径（文件夹）");
    }
    if (!path) return;
    const res = await fetch("/api/workspaces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, activate: true }),
    }).then((r) => r.json());
    if (res.error) {
      addMeta(res.error);
      return;
    }
    if (desktop && desktop.setWorkspace) await desktop.setWorkspace(path);
    const rt = await fetch("/api/runtime").then((r) => r.json());
    fillSettingsForm(rt);
    currentWorkspace = rt.workspace || path;
    expanded.add(currentWorkspace);
    persistExpanded();
    await refreshSidebar();
    addMeta("已添加工作区 " + folderName(path));
  }

  function openDrawer(name) {
    $(`${name}-mask`).hidden = false;
    const el = $(`${name}-drawer`);
    el.setAttribute("aria-hidden", "false");
    requestAnimationFrame(() => el.classList.add("open"));
  }

  function closeDrawer(name) {
    const el = $(`${name}-drawer`);
    el.classList.remove("open");
    el.setAttribute("aria-hidden", "true");
    setTimeout(() => {
      $(`${name}-mask`).hidden = true;
    }, 160);
  }

  async function loadInfo() {
    const data = await fetch("/api/info").then((r) => r.json());
    els.headerModel.textContent = data.model || "model";
    setWsChip(data.workspace || "");
    currentWorkspace = data.workspace || "";
    if (data.settings) {
      settings = { ...settings, ...data.settings };
      applyTheme(settings.theme || "dark");
    }
    if (data.runtime) fillSettingsForm(data.runtime);
    return data;
  }

  async function refreshFiles() {
    const data = await fetch("/api/workspace/tree?depth=2").then((r) => r.json());
    els.fileTree.innerHTML = "";
    if (data.error) {
      els.fileTree.textContent = data.error;
      return;
    }
    const byParent = {};
    (data.entries || []).forEach((e) => {
      const parts = e.path.split("/");
      const parent = parts.length === 1 ? "" : parts.slice(0, -1).join("/");
      (byParent[parent] ||= []).push(e);
    });
    function renderLevel(parent, depth) {
      (byParent[parent] || []).forEach((e) => {
        const row = document.createElement("button");
        row.type = "button";
        row.className = "file-row " + e.type;
        row.style.paddingLeft = 0.35 + depth * 0.7 + "rem";
        row.innerHTML = `<span class="ico">${e.type === "dir" ? "▸" : "·"}</span><span>${esc(e.name)}</span>`;
        row.onclick = () => {
          if (e.type === "file") openFile(e.path);
        };
        els.fileTree.appendChild(row);
        if (e.type === "dir") renderLevel(e.path, depth + 1);
      });
    }
    renderLevel("", 0);
  }

  function setFileStatus(msg, kind) {
    const el = $("file-status");
    el.textContent = msg || "";
    el.className = "file-status" + (kind ? " " + kind : "");
  }

  async function openFile(path) {
    const data = await fetch("/api/workspace/file?path=" + encodeURIComponent(path)).then((r) => r.json());
    if (data.error) {
      addMeta(data.error);
      return;
    }
    if (data.binary) {
      addMeta("binary file — cannot edit");
      return;
    }
    openFilePath = data.path;
    fileDirty = false;
    $("file-modal-title").textContent = data.path + (data.truncated ? " (truncated)" : "");
    $("file-modal-body").value = data.content || "";
    $("file-modal-body").readOnly = !!data.truncated;
    $("file-save").disabled = !!data.truncated;
    setFileStatus(data.truncated ? "read-only" : "ready");
    $("file-mask").hidden = false;
    $("file-modal").hidden = false;
    requestAnimationFrame(() => $("file-modal").classList.add("open"));
  }

  function closeFile() {
    if (fileDirty && !confirm("Discard unsaved changes?")) return;
    $("file-modal").classList.remove("open");
    setTimeout(() => {
      $("file-mask").hidden = true;
      $("file-modal").hidden = true;
      openFilePath = "";
      fileDirty = false;
    }, 160);
  }

  async function saveFile() {
    if (!openFilePath || $("file-modal-body").readOnly) return;
    const res = await fetch("/api/workspace/file", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: openFilePath, content: $("file-modal-body").value }),
    }).then((r) => r.json());
    if (res.error) {
      setFileStatus(res.error, "err");
      return;
    }
    fileDirty = false;
    setFileStatus(`saved · ${res.size} bytes`, "ok");
  }

  async function createEntry(kind) {
    const name = prompt(kind === "dir" ? "Folder path" : "File path", kind === "dir" ? "new-folder" : "untitled.md");
    if (!name) return;
    const res = await fetch("/api/workspace/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: name, kind }),
    }).then((r) => r.json());
    if (res.error) {
      addMeta(res.error);
      return;
    }
    await refreshFiles();
    if (kind === "file") openFile(res.path);
  }

  async function switchSession(id) {
    sessionId = id;
    localStorage.setItem("cai_session", id);
    const sess = allSessions.find((s) => s.id === id);
    els.headerTitle.textContent = (sess && sess.preview) || id.slice(0, 10) + "…";
    clearChatKeepHero();
    streamEl = null;
    const data = await fetch(`/api/session/${encodeURIComponent(id)}/transcript`).then((r) => r.json());
    (data.messages || []).forEach((m) => {
      if (m.role === "user") addUser(m.content || "");
      else if (m.role === "assistant" && m.content) addAssistant(m.content);
      else if (m.role === "tool") addToolCard(m.name || "tool", "", m.content || "");
    });
    await refreshSidebar();
  }

  async function newSession() {
    const data = await fetch("/api/session/new", { method: "POST" }).then((r) => r.json());
    sessionId = data.session_id;
    localStorage.setItem("cai_session", sessionId);
    els.headerTitle.textContent = "New conversation";
    clearChatKeepHero();
    streamEl = null;
    if (data.workspace) {
      currentWorkspace = data.workspace;
      expanded.add(data.workspace);
      persistExpanded();
    }
    await refreshSidebar();
  }

  async function sendMessage() {
    const text = els.input.value.trim();
    if (!text || turnActive) return;
    els.input.value = "";
    addUser(text);
    streamEl = null;
    sawStream = false;
    setRunning(true);
    const body = { message: text };
    if (sessionId) body.session_id = sessionId;
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => r.json());
    if (res.session_id) {
      sessionId = res.session_id;
      localStorage.setItem("cai_session", sessionId);
      els.headerTitle.textContent = text.slice(0, 40) || sessionId.slice(0, 10) + "…";
    }
    if (res.error) {
      addMeta(res.error);
      setRunning(false);
    }
  }

  try {
    const es = new EventSource("/api/events");
    es.onmessage = (ev) => {
      let p;
      try {
        p = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (p.event === "agent/assistant-stream") {
        if (p.session_id && sessionId && p.session_id !== sessionId) return;
        const body = ensureStream();
        sawStream = true;
        body.innerHTML = renderMd((body.dataset.raw || "") + (p.delta || ""));
        body.dataset.raw = (body.dataset.raw || "") + (p.delta || "");
        els.chat.scrollTop = els.chat.scrollHeight;
      } else if (p.event === "agent/thinking") {
        if (p.session_id && sessionId && p.session_id !== sessionId) return;
        const pre = ensureThinking();
        pre.textContent = (pre.textContent || "") + (p.delta || "");
      } else if (p.event === "agent/phase") {
        if (p.phase === "tool") addToolCard(p.name || "tool", p.summary || "", null);
        else if (p.phase === "tool_done") addMeta("✓ " + (p.name || "tool") + " done");
      } else if (p.event === "agent/end") {
        streamEl = null;
        thinkingEl = null;
        setRunning(false);
        refreshSidebar();
      } else if (p.event === "agent/error") {
        addMeta(p.error || "error");
        setRunning(false);
      }
    };
  } catch (_) {}

  els.send.onclick = sendMessage;
  els.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  $("btn-new").onclick = newSession;
  $("btn-files-refresh").onclick = refreshFiles;
  $("btn-file-new").onclick = () => createEntry("file");
  $("btn-dir-new").onclick = () => createEntry("dir");
  $("file-save").onclick = saveFile;
  $("file-modal-body").addEventListener("input", () => {
    fileDirty = true;
    setFileStatus("unsaved");
  });
  $("btn-theme").onclick = () => {
    applyTheme(settings.theme === "light" ? "dark" : "light");
    fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme: settings.theme }),
    });
  };
  $("btn-settings").onclick = async () => {
    const rt = await fetch("/api/runtime").then((r) => r.json());
    fillSettingsForm(rt);
    openDrawer("settings");
  };
  $("settings-close").onclick = () => closeDrawer("settings");
  $("settings-mask").onclick = () => closeDrawer("settings");
  $("btn-files-open").onclick = async () => {
    await refreshFiles();
    openDrawer("files");
  };
  $("files-close").onclick = () => closeDrawer("files");
  $("files-mask").onclick = () => closeDrawer("files");
  $("set-provider").onchange = () => {
    const prov = $("set-provider").value;
    const cur = $("set-base-url").value.trim();
    if (prov === "anthropic") {
      if (!cur || cur.includes("localhost") || cur.includes("openai.com") || cur.endsWith("/v1")) {
        $("set-base-url").value = "https://api.anthropic.com";
      }
      if (!$("set-model").value || $("set-model").value.includes("/")) {
        $("set-model").value = "claude-sonnet-4-5";
      }
    } else if (!cur || cur.includes("anthropic.com")) {
      $("set-base-url").value = "https://api.openai.com/v1";
    }
  };
  $("settings-save").onclick = async () => {
    const body = {
      provider: $("set-provider").value,
      base_url: $("set-base-url").value.trim(),
      model: $("set-model").value.trim(),
      max_steps: Number($("set-max-steps").value) || 16,
      stream: $("set-stream").checked,
      debug: $("set-debug").checked,
      theme: $("set-theme").value,
      approval: $("set-approval").value,
    };
    const key = $("set-api-key").value.trim();
    if (key) body.api_key = key;
    const rt = await fetch("/api/runtime", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => r.json());
    if (rt.error) {
      addMeta(rt.error);
      return;
    }
    fillSettingsForm(rt);
    settings.theme = rt.theme || body.theme;
    applyTheme(settings.theme);
    els.headerModel.textContent = rt.model || "model";
    setWsChip(rt.workspace || "");
    closeDrawer("settings");
  };
  $("btn-ws-add").onclick = addWorkspace;
  $("btn-hero-ws").onclick = addWorkspace;
  $("btn-hero-settings").onclick = () => $("btn-settings").click();
  $("btn-ws-search").onclick = () => {
    const wrap = $("ws-search-wrap");
    wrap.hidden = !wrap.hidden;
    $("btn-ws-search").classList.toggle("active", !wrap.hidden);
    if (!wrap.hidden) $("ws-search").focus();
  };
  $("ws-search").addEventListener("input", () => {
    wsQuery = $("ws-search").value || "";
    renderTree();
  });
  $("btn-ws-filter").onclick = () => {
    filterHasSessions = !filterHasSessions;
    localStorage.setItem("cai_ws_filter", filterHasSessions ? "1" : "0");
    renderTree();
  };
  $("btn-fetch-models").onclick = async () => {
    const status = $("models-fetch-status");
    status.textContent = "拉取中…";
    const body = {
      provider: $("set-provider").value,
      base_url: $("set-base-url").value.trim(),
      api_key: $("set-api-key").value.trim(),
    };
    const res = await fetch("/api/models/discover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => r.json());
    if (res.error) {
      status.textContent = res.error;
      return;
    }
    populateModelSelect(res.models || [], $("set-model").value || runtime.model);
    status.textContent = `${(res.models || []).length} models`;
  };
  $("set-model-select").onchange = () => {
    if ($("set-model-select").value) {
      $("set-model").value = $("set-model-select").value;
    }
  };
  $("file-close").onclick = closeFile;
  $("file-mask").onclick = closeFile;

  loadInfo().then(async () => {
    await syncDesktopRecents();
    await refreshSidebar();
    if (sessionId) switchSession(sessionId);
  });
})();
