window.MirrorLifePath = (() => {
  const OPEN = "#7a9a78";
  const OPEN_SOFT = "rgba(122, 154, 120, 0.28)";
  const CLOSED = "#d9cbbd";
  const CLOSED_STROKE = "#c9b8a8";
  const TODAY = "#c4785a";
  const TRUNK = "#b08968";
  const GRID = "rgba(196, 120, 90, 0.28)";
  const LABEL = "#8a7668";
  const FONT = "Noto Sans SC, Songti SC, sans-serif";

  function clear(svg) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
  }

  function el(name, attrs = {}, text) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
    if (text != null) node.textContent = text;
    return node;
  }

  function layout(data) {
    const trunk = data?.past?.trunk || [];
    const closed = data?.past?.closed || [];
    const months = data?.future?.months || [];
    const W = 1100;
    const H = 420;
    const todayX = 420;
    const leftPad = 48;
    const rightPad = 40;
    const midY = H / 2;

    const positions = new Map();
    const nodes = [];

    // Past trunk along a gentle sine
    const trunkCount = Math.max(trunk.length, 1);
    trunk.forEach((n, i) => {
      const t = trunkCount === 1 ? 0.5 : i / (trunkCount - 1);
      const x = leftPad + t * (todayX - 70 - leftPad);
      const y = midY + Math.sin(t * Math.PI) * 36;
      positions.set(n.id, { x, y, kind: "trunk", data: n });
      nodes.push({ ...n, kind: "trunk", x, y });
    });

    // Today
    const today = {
      id: "today",
      label: data?.today_label || "你的人生 · 今天",
      detail: data?.summary || "",
      kind: "today",
      x: todayX,
      y: midY,
    };
    positions.set("today", today);
    nodes.push(today);

    // Closed branches off trunk / today
    closed.forEach((n, i) => {
      const fromId = n.from && positions.has(n.from) ? n.from : (trunk[trunk.length - 1]?.id || "today");
      const origin = positions.get(fromId) || today;
      const side = i % 2 === 0 ? -1 : 1;
      const x = origin.x + 18 + (i % 3) * 16;
      const y = origin.y + side * (42 + (i % 4) * 28);
      positions.set(n.id, { x, y, kind: "closed", data: n });
      nodes.push({ ...n, kind: "closed", x, y, fromId });
    });

    // Future months
    const monthXs = months.map((_, i) => {
      const span = W - todayX - rightPad;
      return todayX + 90 + (i + 1) * (span / (months.length + 0.2));
    });
    const idToMonthNode = new Map();

    months.forEach((month, mi) => {
      const list = month.nodes || [];
      const x = monthXs[mi];
      list.forEach((n, ni) => {
        const spread = Math.max(list.length - 1, 1);
        const y = midY + (ni - spread / 2) * 72;
        const item = { ...n, kind: "open", x, y, month: month.month };
        positions.set(n.id, item);
        idToMonthNode.set(n.id, item);
        nodes.push(item);
      });
    });

    const edges = [];
    // trunk chain → today
    for (let i = 1; i < trunk.length; i++) {
      edges.push({
        from: positions.get(trunk[i - 1].id),
        to: positions.get(trunk[i].id),
        kind: "trunk",
      });
    }
    if (trunk.length) {
      edges.push({
        from: positions.get(trunk[trunk.length - 1].id),
        to: today,
        kind: "trunk",
      });
    }

    closed.forEach((n) => {
      const to = positions.get(n.id);
      const from = positions.get(n.from) || positions.get(trunk[trunk.length - 1]?.id) || today;
      if (to && from) edges.push({ from, to, kind: "closed" });
    });

    // future: month1 from today; later months from parent or previous month centroid
    months.forEach((month, mi) => {
      (month.nodes || []).forEach((n) => {
        const to = positions.get(n.id);
        if (!to) return;
        let from;
        if (mi === 0) from = today;
        else if (n.parent && positions.has(n.parent)) from = positions.get(n.parent);
        else {
          const prev = months[mi - 1]?.nodes?.[0];
          from = prev ? positions.get(prev.id) : today;
        }
        edges.push({ from, to, kind: "open" });
      });
    });

    return { W, H, todayX, midY, nodes, edges, months };
  }

  function curve(a, b) {
    const mx = (a.x + b.x) / 2;
    return `M ${a.x} ${a.y} C ${mx} ${a.y}, ${mx} ${b.y}, ${b.x} ${b.y}`;
  }

  function render(svg, data, { onSelect } = {}) {
    clear(svg);
    const L = layout(data);
    svg.setAttribute("viewBox", `0 0 ${L.W} ${L.H}`);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");

    // TODAY line
    svg.appendChild(
      el("line", {
        x1: L.todayX,
        y1: 18,
        x2: L.todayX,
        y2: L.H - 28,
        stroke: GRID,
        "stroke-width": 1.5,
        "stroke-dasharray": "5 6",
      })
    );
    svg.appendChild(
      el(
        "text",
        {
          x: L.todayX,
          y: 14,
          fill: LABEL,
          "text-anchor": "middle",
          "font-family": FONT,
          "font-size": 12,
        },
        "今天"
      )
    );
    svg.appendChild(
      el(
        "text",
        {
          x: 48,
          y: L.H - 10,
          fill: LABEL,
          "font-family": FONT,
          "font-size": 12,
        },
        "← 走过的路"
      )
    );
    svg.appendChild(
      el(
        "text",
        {
          x: L.W - 40,
          y: L.H - 10,
          fill: LABEL,
          "text-anchor": "end",
          "font-family": FONT,
          "font-size": 12,
        },
        "还可能去的地方 →"
      )
    );

    // Month labels
    L.months.forEach((month) => {
      const nodes = (month.nodes || [])
        .map((n) => L.nodes.find((x) => x.id === n.id))
        .filter(Boolean);
      if (!nodes.length) return;
      const x = nodes[0].x;
      svg.appendChild(
        el(
          "text",
          {
            x,
            y: 28,
            fill: OPEN,
            "text-anchor": "middle",
            "font-family": FONT,
            "font-size": 12,
          },
          month.label || `第 ${month.month} 月`
        )
      );
    });

    const edgeLayer = el("g");
    const nodeLayer = el("g");
    svg.appendChild(edgeLayer);
    svg.appendChild(nodeLayer);

    L.edges.forEach((e) => {
      if (!e.from || !e.to) return;
      const isClosed = e.kind === "closed";
      edgeLayer.appendChild(
        el("path", {
          d: curve(e.from, e.to),
          fill: "none",
          stroke: isClosed ? CLOSED_STROKE : e.kind === "trunk" ? TRUNK : OPEN,
          "stroke-width": e.kind === "trunk" ? 3.4 : isClosed ? 1.4 : 2,
          opacity: isClosed ? 0.7 : 1,
        })
      );
    });

    L.nodes.forEach((n) => {
      const g = el("g", { class: "path-node", "data-id": n.id, style: "cursor:pointer" });
      const w = n.kind === "today" ? 108 : 86;
      const h = n.kind === "today" ? 36 : 28;
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
      g.appendChild(
        el("rect", {
          x: n.x - w / 2,
          y: n.y - h / 2,
          width: w,
          height: h,
          rx: 14,
          fill,
          stroke,
          "stroke-width": n.kind === "today" ? 2 : 1,
        })
      );
      const label = (n.label || "").slice(0, 12);
      g.appendChild(
        el(
          "text",
          {
            x: n.x,
            y: n.y + 4,
            fill: textFill,
            "text-anchor": "middle",
            "font-family": FONT,
            "font-size": n.kind === "today" ? 11 : 10,
          },
          label
        )
      );
      g.addEventListener("click", () => onSelect && onSelect(n));
      nodeLayer.appendChild(g);
    });

    // Soft open glow under future edges
    edgeLayer.appendChild(
      el("path", {
        d: "",
        fill: OPEN_SOFT,
        opacity: 0,
      })
    );
  }

  function renderHistory(listEl, history, { onPick } = {}) {
    listEl.innerHTML = "";
    if (!history?.length) {
      listEl.innerHTML = `<p class="history-empty">抽屉还是空的。浇进一点生活之后，旧地图会收在这里。</p>`;
      return;
    }
    [...history].reverse().forEach((h) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "history-item";
      const when = (h.archived_at || "").replace("T", " ").slice(0, 19);
      const reasonMap = {
        "water:note": "写了一句日记",
        "water:upload": "放进了文件",
        manual: "重新想了一遍",
        boot: "刚醒来的样子",
      };
      const reason = reasonMap[h.reason] || h.reason || "旧地图";
      btn.innerHTML = `<strong>${reason}</strong><span>${when}</span><em>${
        h.summary || ""
      }</em>`;
      btn.addEventListener("click", () => onPick && onPick(h));
      listEl.appendChild(btn);
    });
  }

  return { render, renderHistory };
})();
