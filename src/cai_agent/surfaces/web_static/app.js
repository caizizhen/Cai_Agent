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
  let lastStreamEl = null;
  let sawStream = false;
  /** @type {{id:string,name:string,mime:string,data:string,preview:string}[]} */
  let pendingImages = [];
  const MAX_PENDING_IMAGES = 6;
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
  let modelProfiles = [];
  let activeModelId = "";
  let editingProfileId = "";
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
    if ($("composer-model-btn")) $("composer-model-btn").disabled = on;
    if (on) closeModelPicker();
    if ($("composer-approval")) $("composer-approval").disabled = on;
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

  function focusComposer() {
    try {
      if (!els.input) return;
      // Electron often loses focus after native dialogs / DOM rebuilds.
      requestAnimationFrame(() => {
        els.input.focus({ preventScroll: true });
      });
    } catch (_) {}
  }

  function resetInteractionState({ focus = true } = {}) {
    setRunning(false);
    streamEl = null;
    lastStreamEl = null;
    thinkingEl = null;
    sawStream = false;
    hideApprove();
    closePlusMenu();
    closeModelPicker();
    closeStatsPops();
    closeNoteModal();
    closeConfirmModal(false);
    ["settings-mask", "files-mask", "file-mask", "note-mask", "confirm-mask"].forEach((id) => {
      const el = $(id);
      if (el) el.hidden = true;
    });
    if (focus) focusComposer();
  }

  let confirmResolver = null;

  function closeConfirmModal(result) {
    $("confirm-mask").hidden = true;
    $("confirm-modal").hidden = true;
    const resolve = confirmResolver;
    confirmResolver = null;
    if (resolve) resolve(!!result);
  }

  function confirmDialog(message, title) {
    return new Promise((resolve) => {
      confirmResolver = resolve;
      $("confirm-title").textContent = title || "确认";
      $("confirm-msg").textContent = message || "";
      $("confirm-mask").hidden = false;
      $("confirm-modal").hidden = false;
      setTimeout(() => $("confirm-ok").focus(), 30);
    });
  }

  function showHero(show) {
    if (els.hero) els.hero.style.display = show ? "flex" : "none";
  }

  function clearChatKeepHero() {
    // Drop every chat node except the empty-state hero (incl. Thinking leftovers).
    [...els.chatInner.children].forEach((n) => {
      if (n.id !== "hero") n.remove();
    });
    thinkingEl = null;
    streamEl = null;
    lastStreamEl = null;
    sawStream = false;
    showHero(true);
  }

  function eventForCurrentSession(p) {
    // Strict match only — never accept blank/foreign session traffic.
    if (!sessionId || !p || !p.session_id) return false;
    return p.session_id === sessionId;
  }

  function acceptLiveAgentEvent(p) {
    // After new/switch session, turnActive is false so late SSE cannot recreate Thinking.
    if (!turnActive) return false;
    return eventForCurrentSession(p);
  }

  async function cancelActiveRun() {
    const sid = sessionId;
    if (!sid && !turnActive) return;
    try {
      await fetch("/api/cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sid || undefined }),
      });
    } catch (_) {}
    setRunning(false);
    thinkingEl = null;
    streamEl = null;
    lastStreamEl = null;
  }

  function appendNode(node) {
    showHero(false);
    els.chatInner.appendChild(node);
    els.chat.scrollTop = els.chat.scrollHeight;
    return node;
  }

  function fmtTime(iso) {
    if (!iso) {
      const d = new Date();
      return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    }
    const d = new Date(iso);
    if (!Number.isFinite(d.getTime())) return "";
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }

  function fmtTok(n) {
    n = Number(n) || 0;
    if (n >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
    if (n >= 1000) return (n / 1000).toFixed(n >= 10000 ? 0 : 1).replace(/\.0$/, "") + "K";
    return String(n);
  }

  function estimateTokens(text) {
    return Math.max(1, Math.ceil(String(text || "").length / 4));
  }

  function addUser(text, meta) {
    const d = document.createElement("div");
    d.className = "msg msg-user";
    d.dataset.seq = meta && meta.seq != null ? String(meta.seq) : "";
    const images = (meta && meta.images) || [];
    let imgs = "";
    if (images.length) {
      imgs =
        `<div class="msg-images">` +
        images
          .map((img) => {
            const src = img.preview || img.url || "";
            if (!src) return "";
            return `<img src="${esc(src)}" alt="${esc(img.name || "image")}" loading="lazy"/>`;
          })
          .join("") +
        `</div>`;
    }
    d.innerHTML = `${imgs}<div class="bubble">${esc(text || (images.length ? "（图片）" : ""))}</div>`;
    appendNode(d);
  }

  function renderPendingImages() {
    const box = $("composer-attach");
    if (!box) return;
    box.innerHTML = "";
    if (!pendingImages.length) {
      box.hidden = true;
      return;
    }
    box.hidden = false;
    pendingImages.forEach((img) => {
      const chip = document.createElement("div");
      chip.className = "attach-chip";
      chip.innerHTML = `<img src="${esc(img.preview)}" alt="${esc(img.name)}"/><button type="button" class="rm" title="移除">×</button>`;
      chip.querySelector(".rm").onclick = (e) => {
        e.stopPropagation();
        pendingImages = pendingImages.filter((x) => x.id !== img.id);
        renderPendingImages();
      };
      box.appendChild(chip);
    });
  }

  function fileToDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(reader.error || new Error("read failed"));
      reader.readAsDataURL(file);
    });
  }

  async function addImageFiles(fileList) {
    const files = [...(fileList || [])].filter((f) => f && String(f.type || "").startsWith("image/"));
    if (!files.length) return;
    for (const f of files) {
      if (pendingImages.length >= MAX_PENDING_IMAGES) {
        addMeta(`最多添加 ${MAX_PENDING_IMAGES} 张图片`);
        break;
      }
      if (f.size > 8 * 1024 * 1024) {
        addMeta(`图片过大：${f.name}`);
        continue;
      }
      try {
        const dataUrl = await fileToDataUrl(f);
        const comma = dataUrl.indexOf(",");
        const data = comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
        pendingImages.push({
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          name: f.name || "image.png",
          mime: f.type || "image/png",
          data,
          preview: dataUrl,
        });
      } catch (_) {
        addMeta(`无法读取图片：${f.name}`);
      }
    }
    renderPendingImages();
  }

  function msgSeqFrom(bar) {
    const root = bar && bar.closest(".msg");
    const seq = root && root.dataset.seq;
    return seq != null && seq !== "" ? Number(seq) : null;
  }

  function buildMsgActions(opts) {
    const usage = opts.usage || {};
    const tokens = usage.total_tokens || usage.completion_tokens || estimateTokens(opts.text || "");
    let vote = opts.feedback || "";
    const bar = document.createElement("div");
    bar.className = "msg-actions";
    bar.innerHTML =
      `<button type="button" class="act" data-act="copy" title="复制">⧉</button>` +
      `<button type="button" class="act${vote === "up" ? " active-up" : ""}" data-act="up" title="点赞">👍</button>` +
      `<button type="button" class="act${vote === "down" ? " active-down" : ""}" data-act="down" title="有问题的回答">👎</button>` +
      `<button type="button" class="act" data-act="branch" title="在新对话中分支">⑂</button>` +
      `<span class="act-meta"><span data-role="usage">用量 ${esc(fmtTok(tokens))} tok</span>` +
      `<span data-role="time">${esc(fmtTime(opts.ts))}</span></span>`;
    bar.querySelector('[data-act="copy"]').onclick = async () => {
      const body = bar.closest(".msg") && bar.closest(".msg").querySelector(".body");
      const text = (body && body.dataset.raw) || opts.text || "";
      try {
        await navigator.clipboard.writeText(text);
        addMeta("已复制");
      } catch {
        addMeta("复制失败");
      }
    };
    bar.querySelector('[data-act="up"]').onclick = async () => {
      const next = vote === "up" ? "" : "up";
      await setFeedback(msgSeqFrom(bar), next, bar);
      vote = next;
    };
    bar.querySelector('[data-act="down"]').onclick = async () => {
      const next = vote === "down" ? "" : "down";
      await setFeedback(msgSeqFrom(bar), next, bar);
      vote = next;
    };
    bar.querySelector('[data-act="branch"]').onclick = () => branchFrom(msgSeqFrom(bar));
    return bar;
  }

  function syncToolsTag(approval) {
    const mode = approval || ($("composer-approval") && $("composer-approval").value) || "auto";
    const el = $("header-tools");
    if (!el) return;
    if (mode === "deny") el.textContent = "read";
    else if (mode === "confirm") el.textContent = "read · write* · edit* · bash*";
    else el.textContent = "read · write · edit · bash";
  }

  let pendingApproval = null;

  function hideApprove() {
    pendingApproval = null;
    const box = $("approve");
    if (box) box.classList.remove("show");
  }

  function showApprove(p) {
    pendingApproval = p;
    $("approve-detail").textContent =
      `${p.tool_name || "tool"}` + (p.args ? `\n${p.args}` : "");
    $("approve").classList.add("show");
  }

  async function decideApproval(allow) {
    if (!pendingApproval) return;
    const body = {
      session_id: pendingApproval.session_id || sessionId,
      tool_call_id: pendingApproval.tool_call_id,
      allow: !!allow,
    };
    hideApprove();
    await fetch("/api/approval", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  async function bindLastAssistantMeta(el) {
    if (!sessionId || !el) return;
    try {
      const data = await fetch(`/api/session/${encodeURIComponent(sessionId)}/transcript`).then((r) => r.json());
      const last = [...(data.messages || [])].reverse().find((m) => m.role === "assistant");
      if (last) {
        el.dataset.seq = String(last.seq);
        if (last.ts) {
          const timeEl = el.querySelector('[data-role="time"]');
          if (timeEl) timeEl.textContent = fmtTime(last.ts);
        }
        if (last.usage && (last.usage.total_tokens || last.usage.completion_tokens)) {
          const usageEl = el.querySelector('[data-role="usage"]');
          const tokens = last.usage.total_tokens || last.usage.completion_tokens;
          if (usageEl) usageEl.textContent = `用量 ${fmtTok(tokens)} tok`;
        }
      }
      if (data.stats) updateSessionStats(data.stats);
    } catch (_) {}
  }

  function addAssistant(text, meta) {
    const d = document.createElement("div");
    d.className = "msg msg-assistant";
    d.dataset.seq = meta && meta.seq != null ? String(meta.seq) : "";
    d.innerHTML = `<div class="label">CAI</div><div class="body">${renderMd(text)}</div>`;
    const body = d.querySelector(".body");
    body.dataset.raw = text || "";
    d.appendChild(
      buildMsgActions({
        text: text || "",
        seq: meta && meta.seq,
        ts: meta && meta.ts,
        usage: (meta && meta.usage) || {},
        feedback: (meta && meta.feedback) || "",
      }),
    );
    appendNode(d);
    return d;
  }

  function ensureStream() {
    if (!streamEl) {
      streamEl = addAssistant("", { ts: new Date().toISOString() });
      sawStream = false;
    }
    return streamEl.querySelector(".body");
  }

  async function setFeedback(seq, vote, bar) {
    if (!sessionId || seq == null || seq === "") {
      addMeta("发送后才可反馈");
      return;
    }
    const res = await fetch(`/api/session/${encodeURIComponent(sessionId)}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seq: Number(seq), vote }),
    }).then((r) => r.json());
    if (res.error) {
      addMeta(res.error);
      return;
    }
    bar.querySelector('[data-act="up"]').classList.toggle("active-up", vote === "up");
    bar.querySelector('[data-act="down"]').classList.toggle("active-down", vote === "down");
  }

  async function branchFrom(seq) {
    if (!sessionId) {
      addMeta("无会话可分支");
      return;
    }
    const body = {};
    if (seq != null && seq !== "") body.upto_seq = Number(seq);
    const res = await fetch(`/api/session/${encodeURIComponent(sessionId)}/branch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => r.json());
    if (res.error) {
      addMeta(res.error);
      return;
    }
    addMeta("已分支到新对话");
    await switchSession(res.session_id);
  }

  function fmtDuration(ms) {
    const n = Number(ms) || 0;
    if (n <= 0) return "—";
    if (n < 1000) return `${Math.round(n)}毫秒`;
    const sec = n / 1000;
    if (sec < 60) return `${sec.toFixed(1)}秒`;
    const m = Math.floor(sec / 60);
    const s = Math.round(sec % 60);
    return `${m}分 ${s}秒`;
  }

  function closeStatsPops() {
    ["pop-session", "pop-token"].forEach((id) => {
      const el = $(id);
      if (el) el.hidden = true;
    });
    ["pill-session", "pill-token"].forEach((id) => {
      const el = $(id);
      if (el) el.classList.remove("open");
    });
  }

  function updateSessionStats(stats) {
    if (!stats) return;
    const rounds = stats.rounds || 0;
    const steps = stats.steps || 0;
    const tps = stats.tps || 0;
    const tok = stats.total_tokens || 0;
    const hit = stats.cache_hit_pct || 0;
    $("pill-session-label").textContent =
      `${rounds} 轮 ${steps} 步` + (tps ? ` · ${tps} tok/s` : "");
    $("pill-token-label").textContent =
      `${fmtTok(tok)} tok` + (hit ? ` · 缓存命中 ${hit}%` : "");
    $("stat-model-time").textContent = fmtDuration(stats.model_ms);
    $("stat-tool-time").textContent = fmtDuration(stats.tool_ms);
    $("stat-ttft").textContent = stats.ttft_avg_ms ? fmtDuration(stats.ttft_avg_ms) : "—";
    $("stat-tps").textContent = tps ? `${tps} tok/s` : "—";
    $("stat-token-total").textContent = `${Number(tok).toLocaleString()} tok`;
    $("stat-cache-hit").textContent = hit ? `${hit}%` : "—";
    $("stat-uncached").textContent = `${fmtTok(stats.uncached_input_tokens || 0)} tok`;
    $("stat-cache-read").textContent = `${fmtTok(stats.cache_read_tokens || 0)} tok`;
    $("stat-output").textContent = `${fmtTok(stats.completion_tokens || 0)} tok`;
    const pct = Math.max(0, Math.min(100, Number(stats.context_pct) || 0));
    $("stat-context-pct").textContent = `${pct}%`;
    const fg = $("ctx-fg");
    if (fg) {
      const circ = 2 * Math.PI * 14;
      fg.style.strokeDasharray = String(circ);
      fg.style.strokeDashoffset = String(circ * (1 - pct / 100));
    }
    const ring = $("ctx-ring");
    if (ring) {
      ring.title = `上下文 ${fmtTok(stats.context_used || 0)} / ${fmtTok(stats.context_window || 128000)}`;
    }
  }

  async function refreshSessionStats() {
    if (!sessionId) {
      updateSessionStats({
        total_tokens: 0,
        context_used: 0,
        context_window: 128000,
        context_pct: 0,
        messages: 0,
        rounds: 0,
        steps: 0,
        tps: 0,
        cache_hit_pct: 0,
        uncached_input_tokens: 0,
        cache_read_tokens: 0,
        completion_tokens: 0,
        model_ms: 0,
        tool_ms: 0,
        ttft_avg_ms: 0,
      });
      return;
    }
    try {
      const stats = await fetch(`/api/session/${encodeURIComponent(sessionId)}/stats`).then((r) => r.json());
      updateSessionStats(stats);
    } catch (_) {}
  }

  let notePrefix = "【反馈】";

  function openNoteModal(kind) {
    notePrefix = kind === "goal" ? "【目标】" : "【反馈】";
    $("note-title").textContent = kind === "goal" ? "目标 / 任务" : "反馈";
    $("note-body").value = "";
    $("note-body").placeholder = kind === "goal" ? "描述目标或任务…" : "写下你的反馈…";
    $("note-mask").hidden = false;
    $("note-modal").hidden = false;
    setTimeout(() => $("note-body").focus(), 30);
  }

  function closeNoteModal() {
    $("note-mask").hidden = true;
    $("note-modal").hidden = true;
  }

  function modelLabel(p) {
    if (!p) return "model";
    const name = String(p.name || p.model || p.id || "model").trim();
    return name;
  }

  function closeModelPicker() {
    const menu = $("composer-model-menu");
    const btn = $("composer-model-btn");
    if (menu) menu.hidden = true;
    if (btn) btn.setAttribute("aria-expanded", "false");
  }

  function openModelPicker() {
    const menu = $("composer-model-menu");
    const btn = $("composer-model-btn");
    if (!menu || !btn || btn.disabled) return;
    menu.hidden = false;
    btn.setAttribute("aria-expanded", "true");
  }

  function renderComposerModels() {
    const menu = $("composer-model-menu");
    const label = $("composer-model-label");
    const btn = $("composer-model-btn");
    if (!menu || !label || !btn) return;
    menu.innerHTML = "";
    const profiles = modelProfiles || [];
    const active =
      profiles.find((p) => p.id === activeModelId) ||
      profiles[0] ||
      null;
    label.textContent = active
      ? modelLabel(active)
      : runtime.model_name || runtime.model || "未配置模型";
    btn.title = active
      ? `${active.provider || ""} · ${active.model || ""} · ${active.base_url || ""}`
      : "切换模型";

    if (!profiles.length) {
      const empty = document.createElement("button");
      empty.type = "button";
      empty.className = "mp-manage";
      empty.textContent = "去设置添加模型…";
      empty.onclick = (e) => {
        e.stopPropagation();
        closeModelPicker();
        $("btn-settings").click();
      };
      menu.appendChild(empty);
    } else {
      profiles.forEach((p) => {
        const item = document.createElement("button");
        item.type = "button";
        item.role = "option";
        item.className = p.id === (active && active.id) ? "active" : "";
        const host = String(p.base_url || "").replace(/^https?:\/\//, "");
        item.innerHTML =
          `<span class="mp-name">${esc(modelLabel(p))}</span>` +
          `<span class="mp-sub">${esc(p.model || "")}${host ? " · " + esc(host) : ""}</span>`;
        item.onclick = async (e) => {
          e.stopPropagation();
          closeModelPicker();
          // Always activate — skipping "already active" left a stale engine until toggle.
          await activateModelProfile(p.id);
        };
        menu.appendChild(item);
      });
      const manage = document.createElement("button");
      manage.type = "button";
      manage.className = "mp-manage";
      manage.textContent = "管理模型…";
      manage.onclick = (e) => {
        e.stopPropagation();
        closeModelPicker();
        $("btn-settings").click();
      };
      menu.appendChild(manage);
    }
    btn.disabled = turnActive;
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
    modelProfiles = runtime.models || [];
    activeModelId = runtime.active_model_id || "";
    $("set-max-steps").value = String(runtime.max_steps || 16);
    $("set-approval").value = runtime.approval || "auto";
    $("set-stream").checked = runtime.stream !== false;
    $("set-debug").checked = !!runtime.debug;
    $("set-theme").value = runtime.theme || settings.theme || "dark";
    $("set-workspace-label").textContent = runtime.workspace || "—";
    els.headerModel.textContent = runtime.model_name || runtime.model || "model";
    if ($("composer-approval") && runtime.approval) {
      $("composer-approval").value = runtime.approval;
    }
    if ($("set-approval") && runtime.approval) {
      $("set-approval").value = runtime.approval;
    }
    syncToolsTag(runtime.approval);
    renderModelProfiles();
    renderComposerModels();
    if (!$("model-editor").hidden && editingProfileId) {
      const p = modelProfiles.find((m) => m.id === editingProfileId);
      if (p) fillModelEditor(p);
    }
  }

  function fillModelEditor(p) {
    editingProfileId = p && p.id ? p.id : "";
    $("set-profile-id").value = editingProfileId;
    $("set-profile-name").value = (p && p.name) || "";
    $("set-provider").value = p && p.provider === "anthropic" ? "anthropic" : "openai";
    $("set-base-url").value = (p && p.base_url) || "";
    $("set-model").value = (p && p.model) || "";
    $("set-api-key").value = "";
    $("set-api-key").placeholder = p && p.api_key_set ? "•••••••• (leave blank to keep)" : "api key";
    $("model-editor-title").textContent = editingProfileId ? "编辑模型" : "添加模型";
    populateModelSelect(
      p && p.model ? [{ id: p.model, name: p.model }] : [],
      (p && p.model) || "",
    );
  }

  function openModelEditor(p) {
    fillModelEditor(p || { provider: "openai", base_url: "http://localhost:1234/v1" });
    $("model-editor").hidden = false;
  }

  function closeModelEditor() {
    $("model-editor").hidden = true;
    editingProfileId = "";
    $("models-fetch-status").textContent = "";
  }

  function renderModelProfiles() {
    const box = $("model-profile-list");
    if (!box) return;
    box.innerHTML = "";
    if (!modelProfiles.length) {
      box.innerHTML = '<p class="hint">还没有模型。点击下方「添加模型」配置本地或第三方 API。</p>';
      return;
    }
    modelProfiles.forEach((p) => {
      const active = p.id === activeModelId;
      const row = document.createElement("div");
      row.className = "model-profile" + (active ? " active" : "");
      row.innerHTML =
        `<div class="mp-top"><span class="mp-name">${esc(p.name || p.model || "model")}</span>` +
        (active ? `<span class="mp-badge">当前</span>` : "") +
        `</div>` +
        `<div class="mp-meta">${esc(p.provider)} · ${esc(p.model || "—")}<br/>${esc(p.base_url || "")}</div>` +
        `<div class="mp-actions"></div>`;
      const actions = row.querySelector(".mp-actions");
      if (!active) {
        const useBtn = document.createElement("button");
        useBtn.type = "button";
        useBtn.className = "btn btn-primary btn-tiny";
        useBtn.textContent = "使用";
        useBtn.onclick = () => activateModelProfile(p.id);
        actions.appendChild(useBtn);
      }
      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.className = "btn btn-outline btn-tiny";
      editBtn.textContent = "编辑";
      editBtn.onclick = () => openModelEditor(p);
      actions.appendChild(editBtn);
      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn btn-ghost btn-tiny";
      delBtn.textContent = "删除";
      delBtn.onclick = () => deleteModelProfile(p.id, p.name || p.model);
      actions.appendChild(delBtn);
      box.appendChild(row);
    });
  }

  async function activateModelProfile(id) {
    const rt = await fetch(`/api/models/profiles/${encodeURIComponent(id)}/activate`, {
      method: "POST",
    }).then((r) => r.json());
    if (rt.error) {
      addMeta(rt.error);
      return;
    }
    fillSettingsForm(rt);
    els.headerModel.textContent = rt.model_name || rt.model || "model";
    const host = String(rt.base_url || "").replace(/^https?:\/\//, "");
    addMeta(`模型 → ${rt.model_name || rt.model || id}` + (host ? ` @ ${host}` : ""));
  }

  async function deleteModelProfile(id, label) {
    const ok = await confirmDialog(`删除模型「${label || id}」？`, "删除模型");
    if (!ok) return;
    const rt = await fetch(`/api/models/profiles/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }).then((r) => r.json());
    if (rt.error) {
      addMeta(rt.error);
      return;
    }
    if (editingProfileId === id) closeModelEditor();
    fillSettingsForm(rt);
  }

  async function saveModelProfile() {
    const body = {
      id: $("set-profile-id").value.trim() || undefined,
      name: $("set-profile-name").value.trim() || $("set-model").value.trim() || "model",
      provider: $("set-provider").value,
      base_url: $("set-base-url").value.trim(),
      model: $("set-model").value.trim(),
      activate: true,
    };
    const key = $("set-api-key").value.trim();
    if (key) body.api_key = key;
    if (!body.base_url || !body.model) {
      $("models-fetch-status").textContent = "请填写 Base URL 和 Model id";
      return;
    }
    const rt = await fetch("/api/models/profiles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => r.json());
    if (rt.error) {
      $("models-fetch-status").textContent = rt.error;
      return;
    }
    fillSettingsForm(rt);
    closeModelEditor();
    addMeta("已保存模型 " + (rt.model_name || rt.model));
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
          const b = document.createElement("div");
          b.className = "ws-session" + (s.id === sessionId ? " active" : "");
          b.innerHTML =
            `<button type="button" class="sess-main">` +
            `<span class="sess-title">${esc(s.preview || "新会话")}</span>` +
            `<span class="sess-time">${esc(relativeTime(s.updated_at))}</span>` +
            `</button>` +
            `<button type="button" class="sess-del" title="删除会话">✕</button>`;
          const main = b.querySelector(".sess-main");
          main.onclick = async () => {
            if (!g.isUngrouped && normPath(g.key) !== normPath(currentWorkspace)) {
              await activateWorkspace(g.key, { quiet: true });
            }
            await switchSession(s.id);
          };
          b.querySelector(".sess-del").onclick = (ev) => {
            ev.stopPropagation();
            deleteSession(s.id, s.preview || "新会话");
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
    let rt = data.runtime;
    if (!rt || !(rt.models && rt.models.length)) {
      try {
        rt = await fetch("/api/runtime").then((r) => r.json());
      } catch (_) {}
    }
    if (rt) fillSettingsForm(rt);
    else renderComposerModels();
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
    await cancelActiveRun();
    sessionId = ""; // ignore in-flight SSE while loading
    resetInteractionState({ focus: false });
    clearChatKeepHero();
    sessionId = id;
    localStorage.setItem("cai_session", id);
    const sess = allSessions.find((s) => s.id === id);
    els.headerTitle.textContent = (sess && sess.preview) || id.slice(0, 10) + "…";
    const data = await fetch(`/api/session/${encodeURIComponent(id)}/transcript`).then((r) => r.json());
    clearChatKeepHero();
    (data.messages || []).forEach((m) => {
      if (m.role === "user") addUser(m.content || "", m);
      else if (m.role === "assistant" && m.content) addAssistant(m.content, m);
      else if (m.role === "tool") addToolCard(m.name || "tool", "", m.content || "");
    });
    updateSessionStats(data.stats);
    await refreshSidebar();
    await refreshSessionStats();
    focusComposer();
  }

  async function deleteSession(id, label) {
    const ok = await confirmDialog(
      `删除会话「${label || id}」？\n此操作不可恢复。`,
      "删除会话",
    );
    if (!ok) {
      focusComposer();
      return;
    }
    const res = await fetch(`/api/session/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }).then((r) => r.json());
    if (res.error) {
      addMeta(res.error);
      focusComposer();
      return;
    }
    if (sessionId === id) {
      sessionId = "";
      localStorage.removeItem("cai_session");
      els.headerTitle.textContent = "New conversation";
      clearChatKeepHero();
      pendingImages = [];
      renderPendingImages();
    }
    await refreshSidebar();
    resetInteractionState({ focus: true });
  }

  async function newSession() {
    await cancelActiveRun();
    sessionId = ""; // block leftover Thinking/tool SSE from the previous run
    localStorage.removeItem("cai_session");
    resetInteractionState({ focus: false });
    clearChatKeepHero();
    const data = await fetch("/api/session/new", { method: "POST" }).then((r) => r.json());
    sessionId = data.session_id;
    localStorage.setItem("cai_session", sessionId);
    els.headerTitle.textContent = "New conversation";
    clearChatKeepHero();
    pendingImages = [];
    renderPendingImages();
    if (data.workspace) {
      currentWorkspace = data.workspace;
      expanded.add(data.workspace);
      persistExpanded();
    }
    await refreshSidebar();
    await refreshSessionStats();
    focusComposer();
  }

  async function sendMessage() {
    const text = els.input.value.trim();
    const images = pendingImages.slice();
    if ((!text && !images.length) || turnActive) return;
    els.input.value = "";
    pendingImages = [];
    renderPendingImages();
    addUser(text, {
      images: images.map((img) => ({ name: img.name, preview: img.preview, url: img.preview })),
    });
    streamEl = null;
    sawStream = false;
    setRunning(true);
    const body = {
      message: text,
      images: images.map((img) => ({ name: img.name, mime: img.mime, data: img.data })),
    };
    if (sessionId) body.session_id = sessionId;
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => r.json());
    if (res.session_id) {
      sessionId = res.session_id;
      localStorage.setItem("cai_session", sessionId);
      els.headerTitle.textContent = (text || "图片").slice(0, 40) || sessionId.slice(0, 10) + "…";
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
        if (!acceptLiveAgentEvent(p)) return;
        const body = ensureStream();
        sawStream = true;
        body.innerHTML = renderMd((body.dataset.raw || "") + (p.delta || ""));
        body.dataset.raw = (body.dataset.raw || "") + (p.delta || "");
        els.chat.scrollTop = els.chat.scrollHeight;
      } else if (p.event === "agent/thinking") {
        if (!acceptLiveAgentEvent(p)) return;
        const pre = ensureThinking();
        pre.textContent = (pre.textContent || "") + (p.delta || "");
      } else if (p.event === "agent/phase") {
        if (!acceptLiveAgentEvent(p)) return;
        if (p.phase === "tool") addToolCard(p.name || "tool", p.summary || "", null);
        else if (p.phase === "tool_done") addMeta("✓ " + (p.name || "tool") + " done");
      } else if (p.event === "agent/approval") {
        if (!acceptLiveAgentEvent(p)) return;
        showApprove(p);
      } else if (p.event === "agent/end") {
        if (!eventForCurrentSession(p)) return;
        lastStreamEl = streamEl;
        if (streamEl) {
          const body = streamEl.querySelector(".body");
          const raw = (body && body.dataset.raw) || "";
          const usage = p.usage || {};
          const tokens = usage.total_tokens || usage.completion_tokens || estimateTokens(raw);
          const usageEl = streamEl.querySelector('[data-role="usage"]');
          if (usageEl) usageEl.textContent = `用量 ${fmtTok(tokens)} tok`;
          const timeEl = streamEl.querySelector('[data-role="time"]');
          if (timeEl) timeEl.textContent = fmtTime(new Date().toISOString());
        }
        // Remove ephemeral Thinking shells for this turn.
        [...els.chatInner.querySelectorAll(".thinking-card")].forEach((n) => n.remove());
        streamEl = null;
        thinkingEl = null;
        hideApprove();
        setRunning(false);
        refreshSidebar();
      } else if (p.event === "agent/committed") {
        if (!eventForCurrentSession(p)) return;
        const el = lastStreamEl || [...els.chatInner.querySelectorAll(".msg-assistant")].pop();
        if (el && p.seq != null) {
          el.dataset.seq = String(p.seq);
          if (p.ts) {
            const timeEl = el.querySelector('[data-role="time"]');
            if (timeEl) timeEl.textContent = fmtTime(p.ts);
          }
          const usage = p.usage || {};
          const tokens = usage.total_tokens || usage.completion_tokens;
          if (tokens) {
            const usageEl = el.querySelector('[data-role="usage"]');
            if (usageEl) usageEl.textContent = `用量 ${fmtTok(tokens)} tok`;
          }
        } else if (el) {
          bindLastAssistantMeta(el);
        }
        if (p.stats) updateSessionStats(p.stats);
        else refreshSessionStats();
        lastStreamEl = null;
      } else if (p.event === "agent/error") {
        if (!eventForCurrentSession(p)) return;
        addMeta(p.error || "error");
        hideApprove();
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
  $("btn-model-add").onclick = () => openModelEditor(null);
  $("btn-model-cancel").onclick = closeModelEditor;
  $("btn-model-save-profile").onclick = saveModelProfile;

  function closePlusMenu() {
    const menu = $("plus-menu");
    if (!menu) return;
    menu.hidden = true;
    menu.classList.remove("is-open");
  }

  function openPlusMenu() {
    const menu = $("plus-menu");
    if (!menu) return;
    menu.hidden = false;
    menu.classList.add("is-open");
  }

  function appendToComposer(chunk) {
    const text = String(chunk || "").trim();
    if (!text) return;
    const cur = els.input.value;
    els.input.value = cur ? cur.replace(/\s+$/, "") + "\n" + text : text;
    els.input.focus();
    try {
      els.input.setSelectionRange(els.input.value.length, els.input.value.length);
    } catch (_) {}
  }

  $("btn-plus").onclick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    const menu = $("plus-menu");
    if (menu.classList.contains("is-open") || !menu.hidden) closePlusMenu();
    else openPlusMenu();
  };
  document.addEventListener("click", (e) => {
    const wrap = $("btn-plus") && $("btn-plus").closest(".plus-wrap");
    if (wrap && wrap.contains(e.target)) return;
    closePlusMenu();
  });
  $("plus-menu").querySelectorAll("button").forEach((btn) => {
    btn.onclick = async (e) => {
      e.preventDefault();
      e.stopPropagation();
      closePlusMenu();
      const act = btn.dataset.action;
      if (act === "image") {
        $("image-attach-input").click();
      } else if (act === "file") {
        $("file-attach-input").click();
      } else if (act === "feedback") {
        openNoteModal("feedback");
      } else if (act === "goal") {
        openNoteModal("goal");
      } else if (act === "workspace") {
        addWorkspace();
      }
    };
  });

  $("note-ok").onclick = () => {
    const text = ($("note-body").value || "").trim();
    closeNoteModal();
    if (text) appendToComposer(notePrefix + text);
    else focusComposer();
  };
  $("note-cancel").onclick = () => {
    closeNoteModal();
    focusComposer();
  };
  $("note-close").onclick = () => {
    closeNoteModal();
    focusComposer();
  };
  $("note-mask").onclick = () => {
    closeNoteModal();
    focusComposer();
  };
  $("note-body").addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      closeNoteModal();
      focusComposer();
    } else if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      $("note-ok").click();
    }
  });
  $("confirm-ok").onclick = () => closeConfirmModal(true);
  $("confirm-cancel").onclick = () => closeConfirmModal(false);
  $("confirm-close").onclick = () => closeConfirmModal(false);
  $("confirm-mask").onclick = () => closeConfirmModal(false);
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (!$("confirm-modal").hidden) {
      e.preventDefault();
      closeConfirmModal(false);
    }
  });

  function toggleStatsPop(popId, pillId) {
    const pop = $(popId);
    const pill = $(pillId);
    const willOpen = pop.hidden;
    closeStatsPops();
    if (willOpen) {
      pop.hidden = false;
      pill.classList.add("open");
    }
  }
  $("pill-session").onclick = (e) => {
    e.stopPropagation();
    toggleStatsPop("pop-session", "pill-session");
  };
  $("pill-token").onclick = (e) => {
    e.stopPropagation();
    toggleStatsPop("pop-token", "pill-token");
  };
  document.addEventListener("click", (e) => {
    const bar = $("session-stats");
    if (bar && bar.contains(e.target)) return;
    closeStatsPops();
  });
  $("image-attach-input").onchange = async () => {
    const files = [...($("image-attach-input").files || [])];
    $("image-attach-input").value = "";
    await addImageFiles(files);
  };
  $("file-attach-input").onchange = async () => {
    const files = [...($("file-attach-input").files || [])];
    $("file-attach-input").value = "";
    if (!files.length) return;
    const imageFiles = files.filter((f) => String(f.type || "").startsWith("image/"));
    const otherFiles = files.filter((f) => !String(f.type || "").startsWith("image/"));
    if (imageFiles.length) await addImageFiles(imageFiles);
    const names = [];
    for (const f of otherFiles) {
      const text = await f.text().catch(() => null);
      if (text == null) {
        addMeta(`无法读取 ${f.name}`);
        continue;
      }
      const path = f.name;
      const res = await fetch("/api/workspace/file", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path, content: text }),
      }).then((r) => r.json());
      if (res.error) addMeta(res.error);
      else {
        names.push(path);
        addMeta(`已写入工作区：${path}`);
      }
    }
    if (names.length) {
      appendToComposer("请查看刚添加的文件：" + names.join(", "));
    }
  };

  els.input.addEventListener("paste", async (e) => {
    const items = [...((e.clipboardData && e.clipboardData.items) || [])];
    const imageItems = items.filter((it) => it.type && it.type.startsWith("image/"));
    if (!imageItems.length) return;
    e.preventDefault();
    const files = imageItems.map((it) => it.getAsFile()).filter(Boolean);
    await addImageFiles(files);
  });

  const composerEl = document.querySelector(".composer");
  if (composerEl) {
    ["dragenter", "dragover"].forEach((ev) => {
      composerEl.addEventListener(ev, (e) => {
        e.preventDefault();
        composerEl.classList.add("drag-over");
      });
    });
    ["dragleave", "drop"].forEach((ev) => {
      composerEl.addEventListener(ev, (e) => {
        if (ev === "dragleave" && composerEl.contains(e.relatedTarget)) return;
        composerEl.classList.remove("drag-over");
      });
    });
    composerEl.addEventListener("drop", async (e) => {
      e.preventDefault();
      composerEl.classList.remove("drag-over");
      const files = [...((e.dataTransfer && e.dataTransfer.files) || [])];
      await addImageFiles(files);
    });
  }
  $("composer-approval").onchange = async () => {
    const approval = $("composer-approval").value;
    $("set-approval").value = approval;
    syncToolsTag(approval);
    await fetch("/api/runtime", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approval }),
    });
  };
  $("approve-allow").onclick = () => decideApproval(true);
  $("approve-deny").onclick = () => decideApproval(false);
  $("composer-model-btn").onclick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    const menu = $("composer-model-menu");
    if (!menu) return;
    if (menu.hidden) openModelPicker();
    else closeModelPicker();
  };
  document.addEventListener("click", (e) => {
    const wrap = document.querySelector(".model-picker");
    if (wrap && wrap.contains(e.target)) return;
    closeModelPicker();
  });
  $("set-provider").onchange = () => {
    const prov = $("set-provider").value;
    const cur = $("set-base-url").value.trim();
    if (prov === "anthropic") {
      if (!cur || cur.includes("localhost") || cur.includes("openai.com") || /\/v1$/.test(cur)) {
        $("set-base-url").value = "https://api.anthropic.com";
      }
      if (!$("set-model").value || $("set-model").value.includes("/")) {
        $("set-model").value = "claude-sonnet-4-5";
      }
      if (!$("set-profile-name").value) $("set-profile-name").value = "Claude";
    } else if (!cur || cur.includes("anthropic.com")) {
      $("set-base-url").value = "http://localhost:1234/v1";
      if (!$("set-profile-name").value) $("set-profile-name").value = "Local";
    }
  };
  $("settings-save").onclick = async () => {
    const body = {
      max_steps: Number($("set-max-steps").value) || 16,
      stream: $("set-stream").checked,
      debug: $("set-debug").checked,
      theme: $("set-theme").value,
      approval: $("set-approval").value,
    };
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
    els.headerModel.textContent = rt.model_name || rt.model || "model";
    setWsChip(rt.workspace || "");
    if ($("composer-approval")) $("composer-approval").value = body.approval;
    syncToolsTag(body.approval);
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
    renderComposerModels();
    if (sessionId) await switchSession(sessionId);
    else await refreshSessionStats();
  });
})();
