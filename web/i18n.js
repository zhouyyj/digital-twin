window.TwinI18n = (() => {
  const STRINGS = {
    en: {
      metaDescription:
        "A personal world simulator grounded in evidence, constraints, and actual choices.",
      kicker: "Local",
      brandSub: "Add files and notes. Then see possible paths.",
      tabChat: "Chat",
      tabPaths: "Life path",
      meterCapital: "Capital",
      meterEnergy: "Energy",
      meterEntropy: "Entropy",
      meterMemory: "Memory",
      dropAria: "Drop files to add to memory",
      dropTitle: "Add files",
      dropBody:
        "Drop a diary, photo, or document.<br />A new path is generated. The previous path is saved in History.",
      dropWaiting: "Drop files here",
      noteLabel: "Note",
      notePlaceholder: "What happened today… ⌘/Ctrl + Enter to save",
      noteBtn: "Save note",
      boardBtn: "Compare options",
      simBtn: "Simulate",
      healthConnecting: "Connecting…",
      healthReady: "Connected",
      healthOffline: "Offline",
      healthUnreachable: "Can't connect",
      twinAsleep: "Server is not running.",
      twinAsleepRun:
        "Server is not running. From the project folder run: uvicorn server:app --reload --port 8787",
      chatTitle: "Chat",
      chatPlaceholder:
        "Type a message… Enter to send, Shift+Enter for a new line. Mention “deduce” or “choose” to count the cost.",
      send: "Send",
      pathsTitle: (n = 3) => (n === 1 ? "The next month" : `The next ${n} months`),
      pathsLoading: "Loading…",
      pathsHint: "Prediction is not history. Commit to a node only when you mean it.",
      horizonAria: "How many months ahead",
      horizonValue: (n) => (n === 1 ? "1 month" : `${n} months`),
      horizonLess: "Fewer months",
      horizonMore: "More months",
      resetCam: "Center",
      regen: "Recalculate",
      regenBusy: "Recalculating…",
      pathMapAria: "Life path map",
      close: "Close",
      inspName: "Name",
      inspNote: "Note",
      inspHintEdit: "Edits save automatically. You can also drag the node.",
      inspHintArchive: "This is a previous path. Read only.",
      inspClosed: "Already chosen",
      historyTitle: "History",
      historyEmpty:
        "No previous paths. After you add files, the current path is saved here.",
      historyArchive: "Previous: ",
      historyReasonNote: "Saved a note",
      historyReasonUpload: "Added files",
      historyReasonManual: "Regenerated",
      historyReasonBoot: "Initial",
      historyReasonMigration: "Language migration",
      historyReasonFallback: "Previous path",
      historyView: "View map",
      historySelected: "Viewing",
      backToCurrent: "Back to current",
      modalCancel: "Cancel",
      modalOk: "Run",
      modalBoardTitle: "What are you deciding?",
      modalSimTitle: "Which option to simulate?",
      modalBoardPh: "e.g. stay at a company, or start something of my own",
      modalSimPh: "e.g. spend three months on this product",
      whoYou: "You",
      whoTwin: "Twin model",
      whoAlert: "Blocked",
      whoSystem: "System",
      bootHint:
        "I separate what is observed, inferred, and still unknown. Give me a hypothesis—or add evidence to revise the model.",
      wateredFiles: "Files",
      wateredNote: "Note",
      wateredDone: (files, chunks) =>
        `Saved ${files} file(s), ${chunks} memory piece(s)`,
      wateredMsg: (prefix) =>
        `${prefix} became evidence. The twin model and possible worlds were revised.`,
      watering: (n) => `Uploading ${n} file(s)…`,
      waterFail: "Upload failed",
      regenDone: "Possible worlds recalculated. The prior prediction remains in the archive.",
      boardRunning: "Comparing options…",
      simRunning: "Simulating…",
      noOutput: "(no output)",
      today: "today",
      past: "← past",
      future: "future →",
      month: (n) => `Month ${n}`,
      todayFallback: "Today",
      none: "(none)",
    },
  };

  function t(key, ...args) {
    const val = STRINGS.en[key] ?? key;
    return typeof val === "function" ? val(...args) : val;
  }

  function apply(root = document) {
    document.documentElement.lang = "en";
    root.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      const mode = el.getAttribute("data-i18n-mode") || "text";
      const value = t(key);
      if (typeof value === "function") return;
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
  }

  function init() {
    apply();
    return "en";
  }

  return { t, current: () => "en", apply, init, STRINGS };
})();
