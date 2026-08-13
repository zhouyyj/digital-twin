(() => {
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
  const pathDetail = document.getElementById("pathDetail");
  const historyList = document.getElementById("historyList");
  const historyCount = document.getElementById("historyCount");
  const regenPathBtn = document.getElementById("regenPathBtn");

  let busy = false;
  let modalMode = null;
  let lifePathData = null;
  let viewingArchive = null;

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
        ? "你"
        : role === "mirror"
          ? "镜子"
          : role === "alert"
            ? "镜子轻轻拦住你"
            : "旁白";
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
    const deltas = [];
    if (n.capital_delta != null) deltas.push(`capital ${fmtDelta(n.capital_delta)}`);
    if (n.energy_delta != null) deltas.push(`energy ${fmtDelta(n.energy_delta)}`);
    if (n.entropy_delta != null) deltas.push(`entropy ${fmtDelta(n.entropy_delta)}`);
    pathDetail.innerHTML = `
      <h3>${escapeHtml(n.label || n.id)}</h3>
      <p>${escapeHtml(n.detail || "（无详细说明）")}</p>
      ${
        deltas.length
          ? `<div class="deltas">${deltas.join(" · ")}</div>`
          : n.kind === "closed"
            ? `<div class="deltas">已关闭的岔路</div>`
            : ""
      }
    `;
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
    const view = archive
      ? {
          ...data,
          summary: archive.summary,
          today_label: archive.today_label || data.today_label,
          past: archive.past,
          future: archive.future,
        }
      : data;

    pathSummary.textContent = archive
      ? `历史快照（${archive.reason}）：${archive.summary || ""}`
      : view.summary || "—";

    window.MirrorLifePath.render(pathSvg, view, { onSelect: selectNode });
    window.MirrorLifePath.renderHistory(historyList, data.history || [], {
      onPick: (h) => paintLifePath(data, { archive: h }),
    });
    historyCount.textContent = String((data.history || []).length);
    pathDetail.innerHTML = `<h3>点一点路上的地方</h3><p>陶土色是今天，鼠尾草绿是还开着的路，浅褐是已经关上的门。</p>`;
  }

  async function loadLifePath() {
    const res = await fetch("/api/life-path");
    if (!res.ok) throw new Error(await res.text());
    lifePathData = await res.json();
    paintLifePath(lifePathData);
  }

  async function refreshState() {
    const res = await fetch("/api/state");
    if (!res.ok) throw new Error(await res.text());
    setMeters(await res.json());
  }

  async function boot() {
    addBubble(
      "system",
      "把日记或照片放进左边，镜子会重新长出接下来三个月的路。旧的那张地图会收进「人生小路」下面的抽屉里。"
    );
    try {
      const res = await fetch("/api/health");
      const data = await res.json();
      if (!data.ok) {
        healthLine.textContent = data.error || "灯还没亮";
        addBubble("warn", data.error || "镜子还没醒过来");
        return;
      }
      healthLine.textContent = "灯亮着，慢慢来";
      modelLine.textContent = data.model || "";
      await refreshState();
      await loadLifePath();
    } catch (err) {
      healthLine.textContent = "还连不上";
      addBubble(
        "warn",
        "镜子还没醒来。在项目目录运行：uvicorn server:app --reload --port 8787"
      );
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
        headers: { "Content-Type": "application/json" },
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

  promptEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      composer.requestSubmit();
    }
  });

  function applyWaterResult(data, label) {
    const chunks = (data.results || []).reduce((n, r) => n + r.chunks, 0);
    dropStatus.textContent = `收下了 ${data.results.length} 件，长成 ${chunks} 段记忆`;
    addBubble("system", `${label}写进了记忆。小路改了道，旧地图收进抽屉里了。`);
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
    dropStatus.textContent = `正在收下… ${files.length} 件`;
    drop.classList.add("dragover");
    try {
      const fd = new FormData();
      for (const f of files) fd.append("files", f, f.name);
      const res = await fetch("/api/water/upload", { method: "POST", body: fd });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(errText(data, "upload failed"));
      applyWaterResult(data, "这些文件已经");
    } catch (err) {
      dropStatus.textContent = "这次没收下";
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
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(errText(data, "note failed"));
      noteInput.value = "";
      applyWaterResult(data, "这句日记已经");
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

  regenPathBtn.addEventListener("click", async () => {
    if (busy) return;
    setBusy(true);
    regenPathBtn.textContent = "在想…";
    try {
      const res = await fetch("/api/life-path/regenerate", { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(errText(data, "regen failed"));
      lifePathData = data;
      paintLifePath(lifePathData);
      addBubble("system", "镜子重新想了一遍接下来三个月。上一张地图收进抽屉了。");
    } catch (err) {
      addBubble("warn", String(err.message || err));
    } finally {
      regenPathBtn.textContent = "重新想想";
      setBusy(false);
    }
  });

  function openModal(mode) {
    modalMode = mode;
    modalTitle.textContent = mode === "board" ? "此刻卡在哪里？" : "想走哪一条？";
    modalInput.value = "";
    modalInput.placeholder =
      mode === "board" ? "比如：去大厂，还是自己做点什么" : "比如：先把这个小产品做满三个月";
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
    addBubble("system", mode === "board" ? "镜子在把这件事摊开看看…" : "镜子在按月帮你走一遍…");
    try {
      const res = await fetch(mode === "board" ? "/api/board" : "/api/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          mode === "board" ? { dilemma: text } : { choice: text }
        ),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(errText(data, "sandbox failed"));
      addBubble("mirror", data.output || "(无输出)");
      if (data.state) setMeters(data.state);
    } catch (err) {
      addBubble("warn", String(err.message || err));
    } finally {
      setBusy(false);
    }
  });

  boot();
})();
