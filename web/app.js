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

  let busy = false;
  let modalMode = null;

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

  function addBubble(role, text, extraClass = "") {
    const div = document.createElement("div");
    div.className = `bubble ${role} ${extraClass}`.trim();
    const who =
      role === "you"
        ? "你"
        : role === "mirror"
          ? "镜"
          : role === "alert"
            ? "物理警报"
            : "系统";
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
  }

  async function refreshState() {
    const res = await fetch("/api/state");
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    setMeters(data);
  }

  async function boot() {
    addBubble(
      "system",
      "把文件拖进左侧「浇灌」区，或直接对话。含「推演」「做选择」会消耗物理状态。"
    );
    try {
      const res = await fetch("/api/health");
      const data = await res.json();
      if (!data.ok) {
        healthLine.textContent = data.error || "offline";
        addBubble("warn", data.error || "服务器未就绪（检查 OPENAI_API_KEY）");
        return;
      }
      healthLine.textContent = "local · ready";
      modelLine.textContent = data.model || "";
      await refreshState();
    } catch (err) {
      healthLine.textContent = "server unreachable";
      addBubble(
        "warn",
        "无法连接后端。请在项目根目录运行：uvicorn server:app --reload --port 8787"
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
          } else if (payload.type === "warn") {
            addBubble("warn", payload.text);
          } else if (payload.type === "error") {
            addBubble("warn", payload.text);
          } else if (payload.type === "done") {
            cursor.remove();
            if (payload.state) setMeters(payload.state);
          } else if (payload.type === "status") {
            // ignore or show subtly
          }
        }
      }
      cursor.remove();
      if (!assembled && bodyEl.textContent === "") {
        bodyEl.parentElement?.remove();
      }
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

  async function uploadFiles(fileList) {
    const files = [...fileList];
    if (!files.length) return;
    setBusy(true);
    dropStatus.textContent = `浇灌中… ${files.length} 个文件`;
    drop.classList.add("dragover");
    try {
      const fd = new FormData();
      for (const f of files) fd.append("files", f, f.name);
      const res = await fetch("/api/water/upload", { method: "POST", body: fd });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(errText(data, "upload failed"));
      const chunks = (data.results || []).reduce((n, r) => n + r.chunks, 0);
      dropStatus.textContent = `完成 · ${data.results.length} 文件 / ${chunks} 块`;
      addBubble(
        "system",
        `已浇灌 ${data.results.length} 个文件，写入 ${chunks} 条记忆。`
      );
      if (data.memory_events != null) {
        document.getElementById("m-memory").textContent = String(data.memory_events);
      }
    } catch (err) {
      dropStatus.textContent = "浇灌失败";
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
    const files = e.dataTransfer?.files;
    if (files?.length) uploadFiles(files);
  });

  // Prevent browser opening files when dropped outside
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
      dropStatus.textContent = "日记已写入";
      addBubble("system", "已浇灌一条快速日记。");
      if (data.memory_events != null) {
        document.getElementById("m-memory").textContent = String(data.memory_events);
      }
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

  function openModal(mode) {
    modalMode = mode;
    modalTitle.textContent = mode === "board" ? "/board 困境" : "/simulate 路径";
    modalInput.value = "";
    modalInput.placeholder =
      mode === "board" ? "例如：去大厂还是创业" : "例如：全职做独立产品三个月";
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
    addBubble("system", mode === "board" ? `运行 /board …` : `运行 /simulate …`);
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
