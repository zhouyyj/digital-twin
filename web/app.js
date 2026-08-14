(() => {
  const i18n = window.TwinI18n;
  i18n.init();
  const t = (...args) => i18n.t(...args);

  function apiHeaders(extra = {}) {
    return { "X-UI-Lang": i18n.current(), ...extra };
  }

  const logEl = document.getElementById("log");
  const composer = document.getElementById("composer");
  const promptEl = document.getElementById("prompt");
  const sendBtn = document.getElementById("sendBtn");
  const drop = document.getElementById("drop");
  const fileInput = document.getElementById("fileInput");
  const dropStatus = document.getElementById("dropStatus");
  const noteInput = document.getElementById("noteInput");
  const noteBtn = document.getElementById("noteBtn");
  const healthLine = document.getElementById("healthLine");
  const modelLine = document.getElementById("modelLine");
  const overlay = document.getElementById("overlay");
  const modalTitle = document.getElementById("modalTitle");
  const modalInput = document.getElementById("modalInput");
  const modalCancel = document.getElementById("modalCancel");
  const modalOk = document.getElementById("modalOk");
  const pathSvg = document.getElementById("pathSvg");
  const pathSummary = document.getElementById("pathSummary");
  const historyList = document.getElementById("historyList");
  const historyCount = document.getElementById("historyCount");
  const regenPathBtn = document.getElementById("regenPathBtn");
  const resetCamBtn = document.getElementById("resetCamBtn");
  const horizonMinus = document.getElementById("horizonMinus");
  const horizonPlus = document.getElementById("horizonPlus");
  const horizonValue = document.getElementById("horizonValue");
  const pathsTitle = document.getElementById("pathsTitle");
  const HORIZON_KEY = "digital-twin-horizon";

  function clampHorizon(n) {
    const v = Number(n);
    if (!Number.isFinite(v)) return 3;
    return Math.min(6, Math.max(2, Math.round(v)));
  }

  function readSavedHorizon() {
    try {
      return clampHorizon(localStorage.getItem(HORIZON_KEY) || 3);
    } catch {
      return 3;
    }
  }

  let horizon = readSavedHorizon();
  const inspector = document.getElementById("inspector");
  const inspectorClose = document.getElementById("inspectorClose");
  const inspLabel = document.getElementById("inspLabel");
  const inspDetail = document.getElementById("inspDetail");
  const inspDeltas = document.getElementById("inspDeltas");
  const inspHint = document.getElementById("inspHint");

  let busy = false;
  let modalMode = null;
  let lifePathData = null;
  let viewingArchive = null;
  let selectedNode = null;
  let saveTimer = null;
  let healthKey = "healthConnecting";

  function errText(data, fallback) {
    if (!data) return fallback;
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
    }
    return data.detail ? JSON.stringify(data.detail) : fallback;
  }

  function setMeters(state) {
    if (!state) return;
    const fmt = (n) => (typeof n === "number" ? n.toFixed(2) : "—");
    document.getElementById("m-capital").textContent = fmt(state.capital);
    document.getElementById("m-energy").textContent = fmt(state.energy);
    document.getElementById("m-entropy").textContent = fmt(state.entropy_rate);
    if (state.memory_events != null) {
      document.getElementById("m-memory").textContent = String(state.memory_events);
    }
  }

  function addBubble(role, text) {
    const div = document.createElement("div");
    div.className = `bubble ${role}`;
    const who =
      role === "you"
        ? t("whoYou")
        : role === "mirror"
          ? t("whoTwin")
          : role === "alert"
            ? t("whoAlert")
            : t("whoSystem");
    div.innerHTML = `<div class="who">${who}</div><div class="body"></div>`;
    div.querySelector(".body").textContent = text;
    logEl.appendChild(div);
    logEl.scrollTop = logEl.scrollHeight;
    return div.querySelector(".body");
  }

  function setBusy(on) {
    busy = on;
    sendBtn.disabled = on;
    noteBtn.disabled = on;
    regenPathBtn.disabled = on;
    syncHorizonChrome();
  }

  function showView(name) {
    document.querySelectorAll(".tab").forEach((t) => {
      t.classList.toggle("active", t.dataset.view === name);
    });
    document.getElementById("view-chat").classList.toggle("hidden", name !== "chat");
    document.getElementById("view-paths").classList.toggle("hidden", name !== "paths");
    if (name === "paths" && lifePathData) paintLifePath(lifePathData);
  }

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => showView(tab.dataset.view));
  });

  function selectNode(n) {
    selectedNode = n;
    inspector.hidden = false;
    inspLabel.value = n.label || "";
    inspDetail.value = n.detail || "";
    const readOnly = Boolean(viewingArchive);
    inspLabel.disabled = readOnly;
    inspDetail.disabled = readOnly;
    const deltas = [];
    if (n.capital_delta != null) deltas.push(`${t("deltaCapital")} ${fmtDelta(n.capital_delta)}`);
    if (n.energy_delta != null) deltas.push(`${t("deltaEnergy")} ${fmtDelta(n.energy_delta)}`);
    if (n.entropy_delta != null) deltas.push(`${t("deltaEntropy")} ${fmtDelta(n.entropy_delta)}`);
    if (n.kind === "closed") deltas.push(t("inspClosed"));
    inspDeltas.textContent = deltas.join(" · ");
    inspHint.textContent = readOnly ? t("inspHintArchive") : t("inspHintEdit");
  }

  function closeInspector() {
    selectedNode = null;
    inspector.hidden = true;
  }

  inspectorClose.addEventListener("click", closeInspector);

  function queueEdits() {
    if (!selectedNode || viewingArchive) return;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => persistEdits(selectedNode), 450);
  }

  function applyLocalEdit(node) {
    if (!lifePathData || !node) return;
    if (node.id === "today") {
      lifePathData.today_label = node.label || "";
      if (node.detail != null) lifePathData.summary = node.detail;
      return;
    }
    const visit = (n) => {
      if (n && n.id === node.id) {
        n.label = node.label;
        n.detail = node.detail;
      }
    };
    (lifePathData.past?.trunk || []).forEach(visit);
    (lifePathData.past?.closed || []).forEach(visit);
    (lifePathData.future?.months || []).forEach((m) => (m.nodes || []).forEach(visit));
  }

  inspLabel.addEventListener("input", () => {
    if (!selectedNode) return;
    selectedNode.label = inspLabel.value;
    const title = pathSvg.querySelector(`.path-node[data-id="${selectedNode.id}"] text`);
    const first = title?.querySelector("tspan") || title;
    if (first) first.textContent = inspLabel.value;
    applyLocalEdit(selectedNode);
    queueEdits();
  });

  inspDetail.addEventListener("input", () => {
    if (!selectedNode) return;
    selectedNode.detail = inspDetail.value;
    applyLocalEdit(selectedNode);
    if (selectedNode.id === "today") {
      pathSummary.textContent = inspDetail.value;
    }
    queueEdits();
  });

  async function persistEdits(node) {
    if (!node || viewingArchive) return;
    try {
      await fetch("/api/life-path", {
        method: "PATCH",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          edits: {
            [node.id]: { label: node.label || "", detail: node.detail || "" },
          },
        }),
      });
    } catch {
      /* keep local */
    }
  }

  async function persistPositions(payload) {
    if (viewingArchive) return;
    try {
      await fetch("/api/life-path", {
        method: "PATCH",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload),
      });
    } catch {
      /* keep local */
    }
  }

  function fmtDelta(n) {
    const v = Number(n);
    if (Number.isNaN(v)) return String(n);
    return (v >= 0 ? "+" : "") + v;
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function paintLifePath(data, { archive } = {}) {
    viewingArchive = archive || null;
    closeInspector();
    const view = archive
      ? {
          ...data,
          summary: archive.summary,
          today_label: archive.today_label || data.today_label,
          past: archive.past,
          future: archive.future,
          today_x: archive.today_x,
          today_y: archive.today_y,
        }
      : data;

    pathSummary.textContent = archive
      ? `${t("historyArchive")}${archive.summary || ""}`
      : view.summary || "—";

    const pathLabels = {
      today: t("today"),
      past: t("past"),
      future: t("future"),
      month: (n) => t("month", n),
      todayFallback: t("todayFallback"),
      historyEmpty: t("historyEmpty"),
      historyReasonNote: t("historyReasonNote"),
      historyReasonUpload: t("historyReasonUpload"),
      historyReasonManual: t("historyReasonManual"),
      historyReasonBoot: t("historyReasonBoot"),
      historyReasonFallback: t("historyReasonFallback"),
    };

    window.MirrorLifePath.render(pathSvg, view, {
      readOnly: Boolean(archive),
      onSelect: selectNode,
      onChange: persistPositions,
      labels: pathLabels,
    });
    window.MirrorLifePath.renderHistory(historyList, data.history || [], {
      onPick: (h) => paintLifePath(data, { archive: h }),
      labels: pathLabels,
    });
    historyCount.textContent = String((data.history || []).length);
    if (!archive) {
      const fromMap = data?.meta?.horizon_months;
      if (fromMap) setHorizon(fromMap, { persist: true, silent: true });
    }
  }

  function syncHorizonChrome() {
    if (pathsTitle) pathsTitle.textContent = t("pathsTitle", horizon);
    if (horizonValue) horizonValue.textContent = t("horizonValue", horizon);
    if (horizonMinus) horizonMinus.disabled = busy || horizon <= 2;
    if (horizonPlus) horizonPlus.disabled = busy || horizon >= 6;
    horizonMinus?.setAttribute("aria-label", t("horizonLess"));
    horizonPlus?.setAttribute("aria-label", t("horizonMore"));
    document.querySelector(".horizon-ctl")?.setAttribute("aria-label", t("horizonAria"));
  }

  function setHorizon(next, { persist = true, silent = false } = {}) {
    const clamped = clampHorizon(next);
    const changed = clamped !== horizon;
    horizon = clamped;
    if (persist) {
      try {
        localStorage.setItem(HORIZON_KEY, String(horizon));
      } catch {
        /* ignore */
      }
    }
    syncHorizonChrome();
    if (!silent && changed) regenLifePath();
  }

  async function loadLifePath() {
    const res = await fetch("/api/life-path", { headers: apiHeaders() });
    if (!res.ok) throw new Error(await res.text());
    lifePathData = await res.json();
    paintLifePath(lifePathData);
  }

  async function refreshState() {
    const res = await fetch("/api/state", { headers: apiHeaders() });
    if (!res.ok) throw new Error(await res.text());
    setMeters(await res.json());
  }

  async function boot() {
    addBubble("system", t("bootHint"));
    try {
      const res = await fetch("/api/health", { headers: apiHeaders() });
      const data = await res.json();
      if (!data.ok) {
        healthKey = "healthOffline";
        healthLine.textContent = data.error || t("healthOffline");
        addBubble("warn", data.error || t("twinAsleep"));
        return;
      }
      healthKey = "healthReady";
      healthLine.textContent = t("healthReady");
      modelLine.textContent = data.model || "";
      await refreshState();
      await loadLifePath();
    } catch (err) {
      healthKey = "healthUnreachable";
      healthLine.textContent = t("healthUnreachable");
      addBubble("warn", t("twinAsleepRun"));
    }
  }

  async function sendChat(message) {
    setBusy(true);
    addBubble("you", message);
    const bodyEl = addBubble("mirror", "");
    const cursor = document.createElement("span");
    cursor.className = "cursor";
    bodyEl.appendChild(cursor);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ message }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(errText(err, "chat failed"));
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let assembled = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          const payload = JSON.parse(line.slice(5).trim());
          if (payload.type === "token") {
            assembled += payload.text;
            bodyEl.textContent = assembled;
            bodyEl.appendChild(cursor);
            logEl.scrollTop = logEl.scrollHeight;
          } else if (payload.type === "alert") {
            bodyEl.parentElement.remove();
            addBubble("alert", payload.text);
          } else if (payload.type === "warn" || payload.type === "error") {
            addBubble("warn", payload.text);
          } else if (payload.type === "done") {
            cursor.remove();
            if (payload.state) setMeters(payload.state);
          }
        }
      }
      cursor.remove();
    } catch (err) {
      cursor.remove();
      addBubble("warn", String(err.message || err));
    } finally {
      setBusy(false);
      promptEl.focus();
    }
  }

  composer.addEventListener("submit", (e) => {
    e.preventDefault();
    if (busy) return;
    const message = promptEl.value.trim();
    if (!message) return;
    promptEl.value = "";
    sendChat(message);
  });

  function growComposer() {
    promptEl.style.height = "auto";
    promptEl.style.height = `${Math.min(promptEl.scrollHeight, 160)}px`;
  }
  promptEl.addEventListener("input", growComposer);
  promptEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      composer.requestSubmit();
    }
  });
  composer.addEventListener("submit", () => {
    setTimeout(() => {
      promptEl.style.height = "";
      growComposer();
    }, 0);
  });

  function applyWaterResult(data, label) {
    const chunks = (data.results || []).reduce((n, r) => n + r.chunks, 0);
    dropStatus.textContent = t("wateredDone", data.results.length, chunks);
    addBubble("system", t("wateredMsg", label));
    if (data.memory_events != null) {
      document.getElementById("m-memory").textContent = String(data.memory_events);
    }
    if (data.life_path) {
      lifePathData = data.life_path;
      paintLifePath(lifePathData);
      showView("paths");
    }
  }

  async function uploadFiles(fileList) {
    const files = [...fileList];
    if (!files.length) return;
    setBusy(true);
    dropStatus.textContent = t("watering", files.length);
    drop.classList.add("dragover");
    try {
      const fd = new FormData();
      for (const f of files) fd.append("files", f, f.name);
      const res = await fetch("/api/water/upload", {
        method: "POST",
        headers: apiHeaders(),
        body: fd,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(errText(data, "upload failed"));
      applyWaterResult(data, t("wateredFiles"));
    } catch (err) {
      dropStatus.textContent = t("waterFail");
      addBubble("warn", String(err.message || err));
    } finally {
      drop.classList.remove("dragover");
      setBusy(false);
    }
  }

  drop.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    if (fileInput.files?.length) uploadFiles(fileInput.files);
    fileInput.value = "";
  });

  ["dragenter", "dragover"].forEach((ev) => {
    drop.addEventListener(ev, (e) => {
      e.preventDefault();
      e.stopPropagation();
      drop.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach((ev) => {
    drop.addEventListener(ev, (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (ev === "dragleave") drop.classList.remove("dragover");
    });
  });
  drop.addEventListener("drop", (e) => {
    drop.classList.remove("dragover");
    if (e.dataTransfer?.files?.length) uploadFiles(e.dataTransfer.files);
  });
  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("drop", (e) => e.preventDefault());

  async function sendNote() {
    const note = noteInput.value.trim();
    if (!note || busy) return;
    setBusy(true);
    try {
      const res = await fetch("/api/water/note", {
        method: "POST",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ note }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(errText(data, "note failed"));
      noteInput.value = "";
      applyWaterResult(data, t("wateredNote"));
    } catch (err) {
      addBubble("warn", String(err.message || err));
    } finally {
      setBusy(false);
    }
  }

  noteBtn.addEventListener("click", sendNote);
  noteInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      sendNote();
    }
  });

  resetCamBtn.addEventListener("click", () => {
    pathSvg._resetCamera?.();
  });

  async function regenLifePath() {
    if (busy) return;
    setBusy(true);
    regenPathBtn.textContent = t("regenBusy");
    try {
      const res = await fetch(`/api/life-path/regenerate?months=${horizon}`, {
        method: "POST",
        headers: apiHeaders(),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(errText(data, "regen failed"));
      lifePathData = data;
      paintLifePath(lifePathData);
      addBubble("system", t("regenDone"));
    } catch (err) {
      addBubble("warn", String(err.message || err));
    } finally {
      regenPathBtn.textContent = t("regen");
      setBusy(false);
    }
  }

  regenPathBtn.addEventListener("click", () => regenLifePath());
  horizonMinus.addEventListener("click", () => setHorizon(horizon - 1));
  horizonPlus.addEventListener("click", () => setHorizon(horizon + 1));

  function openModal(mode) {
    modalMode = mode;
    modalTitle.textContent = mode === "board" ? t("modalBoardTitle") : t("modalSimTitle");
    modalInput.value = "";
    modalInput.placeholder = mode === "board" ? t("modalBoardPh") : t("modalSimPh");
    overlay.classList.remove("hidden");
    overlay.setAttribute("aria-hidden", "false");
    modalInput.focus();
  }

  function closeModal() {
    overlay.classList.add("hidden");
    overlay.setAttribute("aria-hidden", "true");
    modalMode = null;
  }

  document.getElementById("boardBtn").addEventListener("click", () => openModal("board"));
  document.getElementById("simBtn").addEventListener("click", () => openModal("sim"));
  modalCancel.addEventListener("click", closeModal);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) closeModal();
  });

  modalOk.addEventListener("click", async () => {
    const text = modalInput.value.trim();
    if (!text || !modalMode) return;
    const mode = modalMode;
    closeModal();
    setBusy(true);
    showView("chat");
    addBubble("system", mode === "board" ? t("boardRunning") : t("simRunning"));
    try {
      const res = await fetch(mode === "board" ? "/api/board" : "/api/simulate", {
        method: "POST",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(
          mode === "board" ? { dilemma: text } : { choice: text }
        ),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(errText(data, "sandbox failed"));
      addBubble("mirror", data.output || t("noOutput"));
      if (data.state) setMeters(data.state);
    } catch (err) {
      addBubble("warn", String(err.message || err));
    } finally {
      setBusy(false);
    }
  });

  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.lang === i18n.current()) return;
      i18n.setLang(btn.dataset.lang);
      healthLine.textContent = t(healthKey);
      if (!busy) dropStatus.textContent = t("dropWaiting");
      regenPathBtn.textContent = t("regen");
      syncHorizonChrome();
      if (lifePathData) paintLifePath(lifePathData, { archive: viewingArchive || undefined });
    });
  });

  syncHorizonChrome();
  boot();
})();
