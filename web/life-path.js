window.MirrorLifePath = (() => {
  const OPEN = "#7a9a78";
  const CLOSED = "#d9cbbd";
  const CLOSED_STROKE = "#c9b8a8";
  const TODAY = "#c4785a";
  const TRUNK = "#b08968";
  const GRID = "rgba(196, 120, 90, 0.28)";
  const LABEL = "#8a7668";
  const FONT = "Noto Sans SC, Songti SC, sans-serif";

  function el(name, attrs = {}, text) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
    if (text != null) node.textContent = text;
    return node;
  }

  function nodeSize(kind) {
    if (kind === "today") return { w: 128, h: 42 };
    return { w: 102, h: 36 };
  }

  function layout(data, labels = {}) {
    const trunk = data?.past?.trunk || [];
    const closed = data?.past?.closed || [];
    const months = data?.future?.months || [];
    const W = 1200;
    const H = 560;
    const todayX = data?.today_x ?? 430;
    const midY = data?.today_y ?? H / 2;
    const leftPad = 56;
    const rightPad = 48;

    const positions = new Map();
    const nodes = [];

    const trunkCount = Math.max(trunk.length, 1);
    trunk.forEach((n, i) => {
      const t = trunkCount === 1 ? 0.5 : i / (trunkCount - 1);
      const x = n.x ?? leftPad + t * (todayX - 80 - leftPad);
      const y = n.y ?? midY + Math.sin(t * Math.PI) * 40;
      const item = { ...n, kind: "trunk", x, y };
      positions.set(n.id, item);
      nodes.push(item);
    });

    const today = {
      id: "today",
      label: data?.today_label || (typeof labels?.todayFallback === "string" ? labels.todayFallback : "Your life · today"),
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
      const x = n.x ?? origin.x + 24 + (i % 3) * 18;
      const y = n.y ?? origin.y + side * (52 + (i % 4) * 32);
      const item = { ...n, kind: "closed", x, y, fromId };
      positions.set(n.id, item);
      nodes.push(item);
    });

    const monthXs = months.map((_, i) => {
      const span = W - todayX - rightPad;
      return todayX + 110 + (i + 1) * (span / (months.length + 0.25));
    });

    months.forEach((month, mi) => {
      const list = month.nodes || [];
      const x0 = monthXs[mi];
      list.forEach((n, ni) => {
        const spread = Math.max(list.length - 1, 1);
        const x = n.x ?? x0;
        const y = n.y ?? midY + (ni - spread / 2) * 84;
        const item = { ...n, kind: "open", x, y, month: month.month };
        positions.set(n.id, item);
        nodes.push(item);
      });
    });

    const edges = [];
    for (let i = 1; i < trunk.length; i++) {
      edges.push({
        fromId: trunk[i - 1].id,
        toId: trunk[i].id,
        kind: "trunk",
      });
    }
    if (trunk.length) {
      edges.push({
        fromId: trunk[trunk.length - 1].id,
        toId: "today",
        kind: "trunk",
      });
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

    return { W, H, todayX, midY, nodes, edges, months, positions };
  }

  function curve(a, b) {
    const mx = (a.x + b.x) / 2;
    return `M ${a.x} ${a.y} C ${mx} ${a.y}, ${mx} ${b.y}, ${b.x} ${b.y}`;
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

    const world = el("g");
    svg.appendChild(world);

    function applyCamera() {
      world.setAttribute(
        "transform",
        `translate(${camera.x} ${camera.y}) scale(${camera.k})`
      );
    }
    applyCamera();

    world.appendChild(
      el("rect", {
        x: -400,
        y: -400,
        width: L.W + 800,
        height: L.H + 800,
        fill: "transparent",
      })
    );

    world.appendChild(
      el("line", {
        x1: L.todayX,
        y1: 8,
        x2: L.todayX,
        y2: L.H - 24,
        stroke: GRID,
        "stroke-width": 1.5,
        "stroke-dasharray": "5 6",
      })
    );
    world.appendChild(
      el("text", {
        x: L.todayX,
        y: 22,
        fill: LABEL,
        "text-anchor": "middle",
        "font-family": FONT,
        "font-size": 13,
      }, labels.today || "today")
    );
    world.appendChild(
      el("text", {
        x: 56,
        y: L.H - 16,
        fill: LABEL,
        "font-family": FONT,
        "font-size": 13,
      }, labels.past || "← the path taken")
    );
    world.appendChild(
      el("text", {
        x: L.W - 48,
        y: L.H - 16,
        fill: LABEL,
        "text-anchor": "end",
        "font-family": FONT,
        "font-size": 13,
      }, labels.future || "places still open →")
    );

    L.months.forEach((month) => {
      const sample = (month.nodes || [])
        .map((n) => byId.get(n.id))
        .filter(Boolean)[0];
      if (!sample) return;
      world.appendChild(
        el("text", {
          x: sample.x,
          y: 36,
          fill: OPEN,
          "text-anchor": "middle",
          "font-family": FONT,
          "font-size": 13,
        }, month.label || (labels.month ? labels.month(month.month) : `Month ${month.month}`))
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
        "stroke-width": e.kind === "trunk" ? 3.6 : e.kind === "closed" ? 1.5 : 2.2,
        opacity: e.kind === "closed" ? 0.7 : 1,
      });
      edgeLayer.appendChild(path);
      edgeEls.push({ el: path, ...e });
    });

    function drawEdges() {
      edgeEls.forEach((e) => {
        const a = byId.get(e.fromId);
        const b = byId.get(e.toId);
        if (!a || !b) return;
        e.el.setAttribute("d", curve(a, b));
      });
    }

    const nodeEls = new Map();

    function paintNode(n) {
      const { w, h } = nodeSize(n.kind);
      let fill = OPEN;
      let stroke = OPEN;
      let textFill = "#f7f4ee";
      if (n.kind === "closed") {
        fill = CLOSED;
        stroke = CLOSED_STROKE;
        textFill = "#6b5b4e";
      } else if (n.kind === "today") {
        fill = TODAY;
        stroke = TODAY;
        textFill = "#fffaf6";
      } else if (n.kind === "trunk") {
        fill = TRUNK;
        stroke = TRUNK;
      }
      const g = el("g", {
        class: "path-node",
        "data-id": n.id,
        style: `cursor:${readOnly ? "pointer" : "grab"}`,
      });
      g.appendChild(
        el("rect", {
          x: -w / 2,
          y: -h / 2,
          width: w,
          height: h,
          rx: 16,
          fill,
          stroke,
          "stroke-width": n.kind === "today" ? 2 : 1,
        })
      );
      g.appendChild(
        el("text", {
          x: 0,
          y: 5,
          fill: textFill,
          "text-anchor": "middle",
          "font-family": FONT,
          "font-size": n.kind === "today" ? 12 : 11,
          "pointer-events": "none",
        }, (n.label || "").slice(0, 12))
      );
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
        const rect = g.querySelector("rect");
        if (rect) rect.setAttribute("stroke-width", nid === id ? 3 : nid === "today" ? 2 : 1);
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
      const next = Math.min(2.4, Math.max(0.45, camera.k * factor));
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

  function renderHistory(listEl, history, { onPick, labels = {} } = {}) {
    listEl.innerHTML = "";
    if (!history?.length) {
      listEl.innerHTML = `<p class="history-empty">${
        labels.historyEmpty || "The drawer is empty."
      }</p>`;
      return;
    }
    [...history].reverse().forEach((h) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "history-item";
      const when = (h.archived_at || "").replace("T", " ").slice(0, 19);
      const reasonMap = {
        "water:note": labels.historyReasonNote || "Wrote a diary line",
        "water:upload": labels.historyReasonUpload || "Added files",
        manual: labels.historyReasonManual || "Thought it through again",
        boot: labels.historyReasonBoot || "How it first woke",
      };
      const reason = reasonMap[h.reason] || h.reason || labels.historyReasonFallback || "Old map";
      btn.innerHTML = `<strong>${reason}</strong><span>${when}</span><em>${
        h.summary || ""
      }</em>`;
      btn.addEventListener("click", () => onPick && onPick(h));
      listEl.appendChild(btn);
    });
  }

  return { render, renderHistory };
})();
