window.MirrorLifePath = (() => {
  const OPEN = "#c9ff54";
  const CLOSED = "#45494b";
  const CLOSED_STROKE = "#3a3d3f";
  const TODAY = "#ff735c";
  const TRUNK = "#8db5ff";
  const LABEL = "#737570";
  const INK = "#eeeae1";
  const INK_SOFT = "#9c9d98";
  const SERIF = "Newsreader, serif";
  const SANS = "Manrope, sans-serif";

  function el(name, attrs = {}, text) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
    if (text != null) node.textContent = text;
    return node;
  }

  function hashStr(s) {
    let h = 0;
    for (let i = 0; i < String(s).length; i++) {
      h = (h * 31 + String(s).charCodeAt(i)) | 0;
    }
    return Math.abs(h);
  }

  function wrapLabel(text, maxChars, maxLines) {
    const raw = String(text || "").trim();
    if (!raw) return [""];
    const isCjk = /[\u4e00-\u9fff]/.test(raw);
    if (isCjk) {
      const lines = [];
      for (let i = 0; i < maxLines; i++) {
        const slice = raw.slice(i * maxChars, (i + 1) * maxChars);
        if (!slice) break;
        lines.push(slice);
      }
      return lines;
    }
    const words = raw.split(/\s+/);
    const lines = [];
    let cur = "";
    for (const w of words) {
      const next = cur ? `${cur} ${w}` : w;
      if (next.length > maxChars && cur) {
        lines.push(cur);
        cur = w;
        if (lines.length === maxLines) return lines;
      } else {
        cur = next;
      }
    }
    if (cur && lines.length < maxLines) lines.push(cur);
    return lines.length ? lines : [raw.slice(0, maxChars)];
  }

  function pebbleSize(kind) {
    if (kind === "today") return { rx: 22, ry: 16 };
    if (kind === "closed") return { rx: 11, ry: 8 };
    if (kind === "trunk") return { rx: 15, ry: 11 };
    return { rx: 18, ry: 13 };
  }

  function pebblePath(id, kind) {
    const { rx, ry } = pebbleSize(kind);
    const h = hashStr(id || "stone");
    const n = 6;
    const pts = [];
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 - 0.28 + ((h % 7) - 3) * 0.02;
      const jx = 0.78 + ((h >> (i * 2)) % 9) / 24;
      const jy = 0.8 + ((h >> (i * 3 + 1)) % 8) / 28;
      pts.push([Math.cos(a) * rx * jx, Math.sin(a) * ry * jy]);
    }
    return pts
      .map((p, i) => `${i === 0 ? "M" : "L"} ${p[0].toFixed(1)} ${p[1].toFixed(1)}`)
      .join(" ") + " Z";
  }

  function layout(data, labels = {}) {
    const trunk = data?.past?.trunk || [];
    const closed = data?.past?.closed || [];
    const months = data?.future?.months || [];
    const nMonths = Math.max(months.length, 1);
    const maxFan = Math.max(3, ...months.map((m) => (m.nodes || []).length), 9);

    const todayX = data?.today_x ?? 340;
    const colGap = 230;
    const W = Math.max(1180, todayX + 90 + nMonths * colGap + 200);
    const H = Math.max(720, 140 + maxFan * 74);
    const midY = data?.today_y ?? H / 2;
    const leftPad = 52;

    const positions = new Map();
    const nodes = [];

    const trunkCount = Math.max(trunk.length, 1);
    trunk.forEach((n, i) => {
      const t = trunkCount === 1 ? 0.5 : i / (trunkCount - 1);
      const wander = ((hashStr(n.id) % 21) - 10);
      const x = n.x ?? leftPad + t * (todayX - 88 - leftPad);
      const y = n.y ?? midY + Math.sin(t * Math.PI) * 28 + wander * 0.4;
      const item = { ...n, kind: "trunk", x, y };
      positions.set(n.id, item);
      nodes.push(item);
    });

    const today = {
      id: "today",
      label: data?.today_label || (typeof labels?.todayFallback === "string" ? labels.todayFallback : "You, here"),
      detail: data?.summary || "",
      kind: "today",
      x: todayX,
      y: midY,
    };
    positions.set("today", today);
    nodes.push(today);

    closed.forEach((n, i) => {
      const fromId =
        n.from && positions.has(n.from)
          ? n.from
          : trunk[trunk.length - 1]?.id || "today";
      const origin = positions.get(fromId) || today;
      const side = i % 2 === 0 ? -1 : 1;
      const x = n.x ?? origin.x + 10 + (i % 3) * 14 + (hashStr(n.id) % 12);
      const y = n.y ?? origin.y + side * (48 + (i % 4) * 28) + ((hashStr(n.id) % 15) - 7);
      const item = { ...n, kind: "closed", x, y, fromId };
      positions.set(n.id, item);
      nodes.push(item);
    });

    const familyYs = [0.2, 0.5, 0.8].map((t) => 70 + t * (H - 140));
    const colX = (mi) => todayX + 118 + mi * colGap;

    months.forEach((month, mi) => {
      const list = month.nodes || [];
      if (mi === 0) {
        list.forEach((n, ni) => {
          const baseY = familyYs[ni] ?? (70 + ((ni + 0.5) / Math.max(list.length, 1)) * (H - 140));
          const xJ = (hashStr(n.id) % 17) - 8;
          const yJ = (hashStr(n.id + "y") % 13) - 6;
          const x = n.x ?? colX(0) + xJ;
          const y = n.y ?? baseY + yJ;
          const item = { ...n, kind: "open", x, y, month: month.month, family: ni };
          positions.set(n.id, item);
          nodes.push(item);
        });
        return;
      }

      const groups = new Map();
      list.forEach((n) => {
        const pid = n.parent && positions.has(n.parent) ? n.parent : "today";
        if (!groups.has(pid)) groups.set(pid, []);
        groups.get(pid).push(n);
      });

      groups.forEach((children, pid) => {
        const parent = positions.get(pid) || today;
        const n = children.length;
        children.forEach((node, ni) => {
          const spread = n === 1 ? 0 : (ni - (n - 1) / 2) * 58;
          const xJ = (hashStr(node.id) % 15) - 7;
          const yJ = (hashStr(node.id + "y") % 11) - 5;
          const x = node.x ?? colX(mi) + xJ;
          const y = node.y ?? parent.y + spread + yJ * 0.35;
          const item = { ...node, kind: "open", x, y, month: month.month };
          positions.set(node.id, item);
          nodes.push(item);
        });
      });
    });

    const edges = [];
    for (let i = 1; i < trunk.length; i++) {
      edges.push({ fromId: trunk[i - 1].id, toId: trunk[i].id, kind: "trunk" });
    }
    if (trunk.length) {
      edges.push({ fromId: trunk[trunk.length - 1].id, toId: "today", kind: "trunk" });
    }
    closed.forEach((n) => {
      edges.push({
        fromId: n.from && positions.has(n.from) ? n.from : trunk[trunk.length - 1]?.id || "today",
        toId: n.id,
        kind: "closed",
      });
    });
    months.forEach((month, mi) => {
      (month.nodes || []).forEach((n) => {
        let fromId = "today";
        if (mi === 0) fromId = "today";
        else if (n.parent && positions.has(n.parent)) fromId = n.parent;
        else fromId = months[mi - 1]?.nodes?.[0]?.id || "today";
        edges.push({ fromId, toId: n.id, kind: "open" });
      });
    });

    return { W, H, todayX, midY, nodes, edges, months, positions, colGap };
  }

  function curve(a, b, kind) {
    const dx = b.x - a.x;
    const wobble = ((hashStr(`${a.id}|${b.id}`) % 19) - 9) * (kind === "closed" ? 1.6 : 0.9);
    const lift = kind === "closed" ? (b.y < a.y ? -22 : 22) : 0;
    const c1x = a.x + dx * 0.42;
    const c2x = a.x + dx * 0.62;
    return `M ${a.x} ${a.y} C ${c1x} ${a.y + wobble + lift}, ${c2x} ${b.y - wobble}, ${b.x} ${b.y}`;
  }

  function addWrappedText(parent, lines, attrs) {
    const text = el("text", attrs);
    lines.forEach((line, i) => {
      const span = el("tspan", { x: attrs.x, dy: i === 0 ? 0 : 15 }, line);
      text.appendChild(span);
    });
    parent.appendChild(text);
    return text;
  }

  function render(svg, data, { onSelect, onChange, readOnly = false, labels = {} } = {}) {
    if (svg._cleanup) svg._cleanup();
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    const L = layout(data, labels);
    const byId = L.positions;
    const camera = svg._camera || { x: 0, y: 0, k: 1 };
    svg._camera = camera;

    svg.setAttribute("viewBox", `0 0 ${L.W} ${L.H}`);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    svg.style.touchAction = "none";
    svg.style.cursor = "grab";

    const defs = el("defs");
    function radial(id, c0, c1) {
      const g = el("radialGradient", {
        id,
        cx: "32%",
        cy: "28%",
        r: "78%",
      });
      g.appendChild(el("stop", { offset: "0%", "stop-color": c0 }));
      g.appendChild(el("stop", { offset: "100%", "stop-color": c1 }));
      defs.appendChild(g);
    }
    radial("pebbleToday", "#ff8d78", "#ff5e48");
    radial("pebbleOpen", "#202425", "#111315");
    radial("pebbleTrunk", "#293441", "#171d24");
    radial("pebbleClosed", "#282a2b", "#161819");
    const drop = el("filter", { id: "pebbleShadow", x: "-40%", y: "-20%", width: "180%", height: "180%" });
    drop.appendChild(el("feDropShadow", {
      dx: "0.6",
      dy: "1.8",
      stdDeviation: "1.4",
      "flood-color": "#000000",
      "flood-opacity": "0.28",
    }));
    defs.appendChild(drop);
    svg.appendChild(defs);

    const world = el("g");
    svg.appendChild(world);

    function applyCamera() {
      world.setAttribute("transform", `translate(${camera.x} ${camera.y}) scale(${camera.k})`);
    }
    applyCamera();

    world.appendChild(
      el("rect", {
        x: -500,
        y: -500,
        width: L.W + 1000,
        height: L.H + 1000,
        fill: "transparent",
      })
    );

    const road = el("path", {
      d: `M 40 ${L.midY} C ${L.todayX * 0.55} ${L.midY - 8}, ${L.todayX * 0.78} ${L.midY + 6}, ${L.todayX} ${L.midY}`,
      fill: "none",
        stroke: "rgba(141, 181, 255, 0.12)",
        "stroke-width": 8,
      "stroke-linecap": "round",
    });
    world.appendChild(road);

    world.appendChild(
      el("text", {
        x: 52,
        y: L.H - 18,
        fill: LABEL,
        "font-family": SERIF,
        "font-size": 13,
        "font-style": "italic",
      }, labels.past || "← the path taken")
    );
    world.appendChild(
      el("text", {
        x: L.W - 48,
        y: L.H - 18,
        fill: LABEL,
        "text-anchor": "end",
        "font-family": SERIF,
        "font-size": 13,
        "font-style": "italic",
      }, labels.future || "places still open →")
    );

    L.months.forEach((month, mi) => {
      const sample = (month.nodes || []).map((n) => byId.get(n.id)).filter(Boolean)[0];
      if (!sample) return;
      world.appendChild(
        el("text", {
          x: sample.x,
          y: 32,
          fill: "rgba(201, 255, 84, 0.72)",
          "text-anchor": "middle",
          "font-family": SERIF,
          "font-size": 12,
          "font-style": "italic",
        }, labels.month ? labels.month(month.month) : `Month ${month.month}`)
      );
    });

    const edgeLayer = el("g");
    const nodeLayer = el("g");
    world.appendChild(edgeLayer);
    world.appendChild(nodeLayer);

    const edgeEls = [];
    L.edges.forEach((e) => {
      const path = el("path", {
        fill: "none",
        stroke: e.kind === "closed" ? CLOSED_STROKE : e.kind === "trunk" ? TRUNK : OPEN,
        "stroke-width": e.kind === "trunk" ? 2.8 : e.kind === "closed" ? 1.15 : 1.7,
        "stroke-linecap": "round",
        "stroke-dasharray": e.kind === "closed" ? "5 7" : e.kind === "open" ? "0" : "0",
        opacity: e.kind === "closed" ? 0.65 : 0.92,
      });
      edgeLayer.appendChild(path);
      edgeEls.push({ el: path, ...e });
    });

    function drawEdges() {
      edgeEls.forEach((e) => {
        const a = byId.get(e.fromId);
        const b = byId.get(e.toId);
        if (!a || !b) return;
        e.el.setAttribute("d", curve(a, b, e.kind));
      });
    }

    const nodeEls = new Map();

    function paintNode(n) {
      const { rx, ry } = pebbleSize(n.kind);
      const fill =
        n.kind === "today"
          ? "url(#pebbleToday)"
          : n.kind === "closed"
            ? "url(#pebbleClosed)"
            : n.kind === "trunk"
              ? "url(#pebbleTrunk)"
              : "url(#pebbleOpen)";
      const stroke = n.plausibility === "breaks"
        ? "#ff735c"
        : n.plausibility === "strained"
          ? "#e6bb5a"
          : n.kind === "today"
            ? "#ff735c"
            : n.kind === "closed"
              ? "#45494b"
              : "#c9ff54";

      const g = el("g", {
        class: "path-node",
        "data-id": n.id,
        style: `cursor:${readOnly ? "pointer" : "grab"}`,
      });

      const d = pebblePath(n.id, n.kind);
      const halo = el("path", {
        class: "halo",
        d,
        fill: "none",
        stroke: n.kind === "today" ? TODAY : OPEN,
        "stroke-width": 7,
        "stroke-linejoin": "miter",
        opacity: n.kind === "today" ? 0.35 : 0,
        transform: "scale(1.18)",
      });
      g.appendChild(halo);

      g.appendChild(
        el("circle", {
          class: "hit",
          r: Math.max(rx, ry) + 16,
          fill: "transparent",
        })
      );

      g.appendChild(
        el("ellipse", {
          cx: 1,
          cy: ry + 2,
          rx: rx * 0.85,
          ry: 4.2,
          fill: "rgba(80, 52, 36, 0.18)",
        })
      );

      g.appendChild(
        el("path", {
          class: "stone",
          d,
          fill,
          stroke,
          "stroke-width": n.kind === "today" ? 2.4 : n.plausibility === "unknown" ? 1 : 1.7,
          "stroke-linejoin": "miter",
          filter: "url(#pebbleShadow)",
        })
      );

      const h = hashStr(n.id);
      g.appendChild(
        el("ellipse", {
          cx: -rx * 0.28,
          cy: -ry * 0.32,
          rx: rx * 0.32,
          ry: ry * 0.18,
          fill: "#ffffff",
          opacity: 0.08,
          "pointer-events": "none",
        })
      );
      g.appendChild(
        el("circle", {
          cx: rx * 0.18,
          cy: ry * 0.08,
          r: 1.4 + (h % 3) * 0.4,
          fill: "rgba(61, 50, 41, 0.18)",
          "pointer-events": "none",
        })
      );
      g.appendChild(
        el("circle", {
          cx: -rx * 0.06,
          cy: ry * 0.28,
          r: 1 + ((h >> 3) % 2) * 0.5,
          fill: "rgba(61, 50, 41, 0.14)",
          "pointer-events": "none",
        })
      );

      const pastSide = n.kind === "trunk" || n.kind === "closed";
      const side = pastSide ? -1 : 1;
      const tx = side * (rx + 14);
      const anchor = side < 0 ? "end" : "start";
      const titleFill = n.kind === "closed" ? "#8a7668" : INK;
      const maxChars = /[\u4e00-\u9fff]/.test(n.label || "") ? 8 : 16;
      const titleLines = wrapLabel(n.label || "", maxChars, 2);
      addWrappedText(g, titleLines, {
        x: tx,
        y: n.kind === "today" ? -2 : -8,
        fill: titleFill,
        "text-anchor": anchor,
        "font-family": SERIF,
        "font-size": n.kind === "today" ? 16 : n.kind === "closed" ? 11 : 14,
        "font-weight": n.kind === "today" ? 650 : 500,
        "pointer-events": "none",
      });

      if (n.kind === "today") {
        g.appendChild(
          el("text", {
            x: tx,
            y: 18,
            fill: LABEL,
            "text-anchor": anchor,
            "font-family": SANS,
            "font-size": 10,
            "pointer-events": "none",
          }, labels.today || "today")
        );
      } else if (n.kind !== "closed" && n.detail) {
        const dChars = /[\u4e00-\u9fff]/.test(n.detail) ? 11 : 26;
        const snippet = wrapLabel(n.detail, dChars, 1)[0];
        g.appendChild(
          el("text", {
            x: tx,
            y: 16 + (titleLines.length > 1 ? 12 : 0),
            fill: INK_SOFT,
            "text-anchor": anchor,
            "font-family": SANS,
            "font-size": 10,
            opacity: 0.88,
            "pointer-events": "none",
          }, snippet)
        );
      }

      g.setAttribute("transform", `translate(${n.x} ${n.y})`);
      return g;
    }

    L.nodes.forEach((n) => {
      const g = paintNode(n);
      nodeLayer.appendChild(g);
      nodeEls.set(n.id, g);
    });
    drawEdges();

    function screenToSvg(evt) {
      const pt = svg.createSVGPoint();
      pt.x = evt.clientX;
      pt.y = evt.clientY;
      const ctm = svg.getScreenCTM();
      if (!ctm) return { x: 0, y: 0 };
      return pt.matrixTransform(ctm.inverse());
    }

    function clientToWorld(evt) {
      const pt = svg.createSVGPoint();
      pt.x = evt.clientX;
      pt.y = evt.clientY;
      const ctm = world.getScreenCTM();
      if (!ctm) return { x: 0, y: 0 };
      return pt.matrixTransform(ctm.inverse());
    }

    let mode = null;
    let dragId = null;
    let start = null;
    let moved = false;

    function highlight(id) {
      nodeEls.forEach((g, nid) => {
        const halo = g.querySelector(".halo");
        if (!halo) return;
        if (nid === id) halo.setAttribute("opacity", "0.95");
        else if (nid === "today") halo.setAttribute("opacity", "0.4");
        else halo.setAttribute("opacity", "0");
      });
    }

    function persistPositions() {
      if (readOnly || !onChange) return;
      const positions = {};
      byId.forEach((n, id) => {
        positions[id] = { x: n.x, y: n.y };
      });
      onChange({ positions });
    }

    function onPointerDown(evt) {
      if (evt.button !== 0) return;
      const target = evt.target.closest?.(".path-node");
      moved = false;
      if (target && !readOnly) {
        dragId = target.getAttribute("data-id");
        mode = "node";
        const n = byId.get(dragId);
        const worldPt = clientToWorld(evt);
        start = { x: worldPt.x - n.x, y: worldPt.y - n.y };
        target.style.cursor = "grabbing";
      } else if (target && readOnly) {
        dragId = target.getAttribute("data-id");
        mode = "tap";
      } else {
        mode = "pan";
        const p = screenToSvg(evt);
        start = { x: p.x - camera.x, y: p.y - camera.y };
        svg.style.cursor = "grabbing";
      }
      svg.setPointerCapture(evt.pointerId);
    }

    function onPointerMove(evt) {
      if (!mode) return;
      if (mode === "pan") {
        const p = screenToSvg(evt);
        camera.x = p.x - start.x;
        camera.y = p.y - start.y;
        applyCamera();
        moved = true;
        return;
      }
      if (mode === "node" && dragId) {
        const pt = clientToWorld(evt);
        const n = byId.get(dragId);
        n.x = pt.x - start.x;
        n.y = pt.y - start.y;
        nodeEls.get(dragId)?.setAttribute("transform", `translate(${n.x} ${n.y})`);
        drawEdges();
        moved = true;
      }
    }

    function onPointerUp() {
      if (!mode) return;
      const id = dragId;
      if (mode === "node" && nodeEls.get(id)) {
        nodeEls.get(id).style.cursor = "grab";
      }
      svg.style.cursor = "grab";
      if (id && !moved) {
        highlight(id);
        onSelect && onSelect(byId.get(id));
      }
      if (mode === "node" && moved) persistPositions();
      mode = null;
      dragId = null;
    }

    function onWheel(evt) {
      evt.preventDefault();
      const P = screenToSvg(evt);
      const factor = evt.deltaY < 0 ? 1.08 : 0.92;
      const next = Math.min(2.4, Math.max(0.4, camera.k * factor));
      const ratio = next / camera.k;
      camera.x = P.x * (1 - ratio) + camera.x * ratio;
      camera.y = P.y * (1 - ratio) + camera.y * ratio;
      camera.k = next;
      applyCamera();
    }

    svg.addEventListener("pointerdown", onPointerDown);
    svg.addEventListener("pointermove", onPointerMove);
    svg.addEventListener("pointerup", onPointerUp);
    svg.addEventListener("pointercancel", onPointerUp);
    svg.addEventListener("wheel", onWheel, { passive: false });

    svg._cleanup = () => {
      svg.removeEventListener("pointerdown", onPointerDown);
      svg.removeEventListener("pointermove", onPointerMove);
      svg.removeEventListener("pointerup", onPointerUp);
      svg.removeEventListener("pointercancel", onPointerUp);
      svg.removeEventListener("wheel", onWheel);
    };

    svg._resetCamera = () => {
      camera.x = 0;
      camera.y = 0;
      camera.k = 1;
      applyCamera();
    };

    return { highlight, byId };
  }

  function renderHistory(listEl, history, { onPick, activeId, labels = {} } = {}) {
    listEl.innerHTML = "";
    if (!history?.length) {
      listEl.innerHTML = `<p class="history-empty">${
        labels.historyEmpty || "No previous paths."
      }</p>`;
      return;
    }
    [...history].reverse().forEach((h) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "history-item";
      if (activeId && h.id === activeId) {
        btn.classList.add("active");
        btn.setAttribute("aria-current", "true");
      }
      const when = (h.archived_at || "").replace("T", " ").slice(0, 19);
      const reasonMap = {
        "water:note": labels.historyReasonNote || "Wrote a diary line",
        "water:upload": labels.historyReasonUpload || "Added files",
        manual: labels.historyReasonManual || "Thought it through again",
        boot: labels.historyReasonBoot || "How it first woke",
        "language-migration": labels.historyReasonMigration || "Language migration",
      };
      const reason = reasonMap[h.reason] || h.reason || labels.historyReasonFallback || "Old map";

      const meta = document.createElement("span");
      meta.className = "history-meta";
      const reasonEl = document.createElement("strong");
      reasonEl.textContent = reason;
      const whenEl = document.createElement("time");
      whenEl.dateTime = h.archived_at || "";
      whenEl.textContent = when || "—";
      meta.append(reasonEl, whenEl);

      const summary = document.createElement("span");
      summary.className = "history-summary";
      summary.textContent = h.summary || labels.historyReasonFallback || "Previous path";

      const action = document.createElement("span");
      action.className = "history-action";
      action.textContent = activeId && h.id === activeId
        ? labels.historySelected || "Viewing"
        : labels.historyView || "View map";

      btn.append(meta, summary, action);
      btn.addEventListener("click", () => onPick && onPick(h));
      listEl.appendChild(btn);
    });
  }

  return { render, renderHistory };
})();
