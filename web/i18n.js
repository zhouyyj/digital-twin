window.TwinI18n = (() => {
  const STRINGS = {
    en: {
      metaDescription:
        "Digital Twin: water it with diaries and photos, then walk the next three months.",
      kicker: "Digital avatar",
      brandSub: "Feed it slowly. The path grows on its own.",
      tabChat: "Chat",
      tabPaths: "Life path",
      meterCapital: "Reserve",
      meterEnergy: "Energy",
      meterEntropy: "Chaos",
      meterMemory: "Memory",
      dropAria: "Drop files to water memory",
      dropTitle: "Water a memory",
      dropBody:
        "Drop in a diary, photo, or document.<br />The twin will grow a new three-month path; the old map goes in the drawer.",
      dropWaiting: "Waiting for a piece of your life",
      noteLabel: "A quick line",
      notePlaceholder: "What happened today… ⌘/Ctrl + Enter to save",
      noteBtn: "Write to memory",
      boardBtn: "Ask around",
      simBtn: "Walk a path",
      healthConnecting: "Lighting the lamp…",
      healthReady: "Lamp’s on. Take your time.",
      healthOffline: "The lamp isn’t lit yet",
      healthUnreachable: "Can’t connect",
      twinAsleep: "The twin isn’t awake yet.",
      twinAsleepRun:
        "The twin isn’t awake. From the project folder run: uvicorn server:app --reload --port 8787",
      chatTitle: "Sit with the twin",
      chatPlaceholder:
        "Say whatever’s on your mind… Enter to send, Shift+Enter for a new line. Mention “deduce” or “choose” to count the cost.",
      send: "Send",
      pathsTitle: "The next three months",
      pathsLoading: "Laying out the path…",
      pathsHint: "Drag nodes · pan the blank space · scroll to zoom",
      resetCam: "Center",
      regen: "Think again",
      regenBusy: "Thinking…",
      pathMapAria: "Life path map",
      close: "Close",
      inspName: "Name",
      inspNote: "This line",
      inspHintEdit: "Edits save on their own. You can also drag the node.",
      inspHintArchive: "This is an old map. Look only.",
      inspClosed: "A door already closed",
      historyTitle: "Earlier maps",
      historyEmpty:
        "The drawer is empty. After you water it, the old map will live here.",
      historyArchive: "Old map: ",
      historyReasonNote: "Wrote a diary line",
      historyReasonUpload: "Added files",
      historyReasonManual: "Thought it through again",
      historyReasonBoot: "How it first woke",
      historyReasonFallback: "Old map",
      modalCancel: "Not now",
      modalOk: "Begin",
      modalBoardTitle: "Where are you stuck?",
      modalSimTitle: "Which path do you want?",
      modalBoardPh: "e.g. big company, or make something of my own",
      modalSimPh: "e.g. give this little product three full months",
      whoYou: "You",
      whoTwin: "Twin",
      whoAlert: "The twin gently stopped you",
      whoSystem: "Aside",
      bootHint:
        "Drop a diary or photo on the left. The twin will grow the next three months; old maps go in the drawer under Life path.",
      wateredFiles: "These files are",
      wateredNote: "That diary line is",
      wateredDone: (files, chunks) =>
        `Took in ${files} file(s), grew ${chunks} memory piece(s)`,
      wateredMsg: (prefix) =>
        `${prefix} written into memory. The path changed; the old map is in the drawer.`,
      watering: (n) => `Taking it in… ${n} file(s)`,
      waterFail: "Didn’t take this time",
      regenDone: "The twin rethought the next three months. The last map is in the drawer.",
      boardRunning: "The twin is spreading this out…",
      simRunning: "The twin is walking this month by month…",
      noOutput: "(nothing came back)",
      deltaCapital: "reserve",
      deltaEnergy: "energy",
      deltaEntropy: "chaos",
      today: "today",
      past: "← the path taken",
      future: "places still open →",
      month: (n) => `Month ${n}`,
      todayFallback: "Your life · today",
      none: "(none)",
    },
    zh: {
      metaDescription: "数字分身：浇灌日记与影像，看看接下来三个月的路。",
      kicker: "数字分身",
      brandSub: "慢慢浇灌，路会自己长出来。",
      tabChat: "聊聊",
      tabPaths: "人生小路",
      meterCapital: "储备",
      meterEnergy: "精力",
      meterEntropy: "混乱",
      meterMemory: "记忆",
      dropAria: "拖放文件以浇灌记忆",
      dropTitle: "浇一杯记忆",
      dropBody:
        "把日记、照片或文档轻轻放进来。<br />分身会重新长出未来三个月的路，旧的那张会收进抽屉。",
      dropWaiting: "等你带来一点生活",
      noteLabel: "随手写一句",
      notePlaceholder: "今天发生了什么… ⌘/Ctrl + Enter 送进去",
      noteBtn: "写入记忆",
      boardBtn: "问一问",
      simBtn: "走一段",
      healthConnecting: "正在点灯…",
      healthReady: "灯亮着，慢慢来。",
      healthOffline: "灯还没亮",
      healthUnreachable: "还连不上",
      twinAsleep: "分身还没醒过来。",
      twinAsleepRun:
        "分身还没醒来。在项目目录运行：uvicorn server:app --reload --port 8787",
      chatTitle: "和分身坐一会儿",
      chatPlaceholder:
        "想说什么就说… Enter 送出，Shift+Enter 换行。提到「推演」或「做选择」时会认真算消耗",
      send: "送出",
      pathsTitle: "接下来三个月",
      pathsLoading: "正在铺开小路…",
      pathsHint: "拖节点改位置 · 空白处拖动画布 · 滚轮缩放",
      resetCam: "回到中心",
      regen: "重新想想",
      regenBusy: "在想…",
      pathMapAria: "人生路径图",
      close: "关闭",
      inspName: "名字",
      inspNote: "这句话",
      inspHintEdit: "可以直接改字，也可以拖着节点走。",
      inspHintArchive: "这是旧地图，只能看看。",
      inspClosed: "已经关上的门",
      historyTitle: "以前的地图",
      historyEmpty: "抽屉还是空的。浇进一点生活之后，旧地图会收在这里。",
      historyArchive: "旧地图：",
      historyReasonNote: "写了一句日记",
      historyReasonUpload: "放进了文件",
      historyReasonManual: "重新想了一遍",
      historyReasonBoot: "刚醒来的样子",
      historyReasonFallback: "旧地图",
      modalCancel: "先算了",
      modalOk: "开始",
      modalBoardTitle: "此刻卡在哪里？",
      modalSimTitle: "想走哪一条？",
      modalBoardPh: "比如：去大厂，还是自己做点什么",
      modalSimPh: "比如：先把这个小产品做满三个月",
      whoYou: "你",
      whoTwin: "分身",
      whoAlert: "分身轻轻拦住你",
      whoSystem: "旁白",
      bootHint:
        "把日记或照片放进左边，分身会重新长出接下来三个月的路。旧的那张地图会收进「人生小路」下面的抽屉里。",
      wateredFiles: "这些文件已经",
      wateredNote: "这句日记已经",
      wateredDone: (files, chunks) =>
        `收下了 ${files} 件，长成 ${chunks} 段记忆`,
      wateredMsg: (prefix) =>
        `${prefix}写进了记忆。小路改了道，旧地图收进抽屉里了。`,
      watering: (n) => `正在收下… ${n} 件`,
      waterFail: "这次没收下",
      regenDone: "分身重新想了一遍接下来三个月。上一张地图收进抽屉了。",
      boardRunning: "分身在把这件事摊开看看…",
      simRunning: "分身在按月帮你走一遍…",
      noOutput: "(无输出)",
      deltaCapital: "储备",
      deltaEnergy: "精力",
      deltaEntropy: "混乱",
      today: "今天",
      past: "← 走过的路",
      future: "还可能去的地方 →",
      month: (n) => `第 ${n} 月`,
      todayFallback: "你的人生 · 今天",
      none: "(无)",
    },
  };

  const KEY = "digital-twin-lang";
  let lang = "en";

  function normalize(value) {
    if (!value) return "en";
    return String(value).toLowerCase().startsWith("zh") ? "zh" : "en";
  }

  function current() {
    return lang;
  }

  function t(key, ...args) {
    const table = STRINGS[lang] || STRINGS.en;
    const fallback = STRINGS.en[key];
    const val = table[key] ?? fallback ?? key;
    return typeof val === "function" ? val(...args) : val;
  }

  function apply(root = document) {
    document.documentElement.lang = lang === "zh" ? "zh-Hans" : "en";
    root.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      const mode = el.getAttribute("data-i18n-mode") || "text";
      const value = t(key);
      if (mode === "html") el.innerHTML = value;
      else el.textContent = value;
    });
    root.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      el.setAttribute("placeholder", t(el.getAttribute("data-i18n-placeholder")));
    });
    root.querySelectorAll("[data-i18n-aria]").forEach((el) => {
      el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria")));
    });
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute("content", t("metaDescription"));
    document.querySelectorAll(".lang-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.lang === lang);
    });
  }

  function setLang(next) {
    lang = normalize(next);
    try {
      localStorage.setItem(KEY, lang);
    } catch {
      /* ignore */
    }
    apply();
    return lang;
  }

  function init() {
    let saved = null;
    try {
      saved = localStorage.getItem(KEY);
    } catch {
      saved = null;
    }
    lang = normalize(saved || "en");
    apply();
    return lang;
  }

  return { t, setLang, current, apply, init, STRINGS };
})();
