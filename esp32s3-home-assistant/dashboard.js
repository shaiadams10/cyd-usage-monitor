// Small enhancement layer for ESPHome web_server v3's built-in log table.
// It intentionally leaves entity rendering and device control to ESPHome.
customElements.whenDefined("esp-log").then(() => {
  const wireLogViewer = () => {
    const app = document.querySelector("esp-app");
    const log = app?.shadowRoot?.querySelector("esp-log");
    const root = log?.shadowRoot;
    const viewport = root?.querySelector(".logs");
    const container = root?.querySelector(".tab-container");

    if (!log || !root || !viewport || !container || log.dataset.scrollEnhanced) {
      return;
    }

    log.dataset.scrollEnhanced = "true";
    log.rows = 300;

    const style = document.createElement("style");
    style.textContent = `
      .codex-log-toolbar {
        align-items: center;
        display: flex;
        gap: 10px;
        justify-content: flex-end;
        margin: 0 0 8px;
      }
      .codex-log-status {
        color: rgba(127, 127, 127, .9);
        font: 12px ui-monospace, monospace;
      }
      .codex-live-button {
        background: #03a9f4;
        border: 0;
        border-radius: 6px;
        color: #fff;
        cursor: pointer;
        font: 600 12px ui-monospace, monospace;
        padding: 7px 11px;
      }
      .codex-live-button:disabled {
        background: rgba(127, 127, 127, .25);
        color: rgba(127, 127, 127, .9);
        cursor: default;
      }
      .logs {
        max-height: min(60vh, 560px);
        overflow: auto !important;
        overscroll-behavior: contain;
      }
    `;
    root.appendChild(style);

    const toolbar = document.createElement("div");
    toolbar.className = "codex-log-toolbar";
    const status = document.createElement("span");
    status.className = "codex-log-status";
    const liveButton = document.createElement("button");
    liveButton.className = "codex-live-button";
    liveButton.type = "button";
    toolbar.append(status, liveButton);
    container.insertBefore(toolbar, viewport);

    let live = true;
    let programmaticScroll = false;

    const atBottom = () =>
      viewport.scrollHeight - viewport.clientHeight - viewport.scrollTop < 12;

    const renderMode = () => {
      status.textContent = live ? "Auto-scroll on" : "Browsing older logs";
      liveButton.textContent = live ? "Live" : "Back to live";
      liveButton.disabled = live;
    };

    const scrollToLive = () => {
      if (!live) return;
      programmaticScroll = true;
      viewport.scrollTop = viewport.scrollHeight;
      requestAnimationFrame(() => {
        programmaticScroll = false;
      });
    };

    viewport.addEventListener("wheel", (event) => {
      if (event.deltaY < 0) {
        live = false;
        renderMode();
      }
    }, {passive: true});

    viewport.addEventListener("scroll", () => {
      if (programmaticScroll) return;
      const nowAtBottom = atBottom();
      if (live !== nowAtBottom) {
        live = nowAtBottom;
        renderMode();
      }
    }, {passive: true});

    liveButton.addEventListener("click", () => {
      live = true;
      renderMode();
      scrollToLive();
    });

    const rows = root.querySelector(".tbody");
    if (rows) {
      new MutationObserver(scrollToLive).observe(rows, {
        childList: true,
        subtree: true,
      });
    }

    renderMode();
    scrollToLive();
  };

  wireLogViewer();
  setInterval(wireLogViewer, 500);
});

// Session History is a URL-addressable dashboard page fed by both structured
// `voice_session: SESSION_JSON ...` device records and the durable acoustic
// diagnostics API. Home Assistant Recorder keeps the source entity history;
// this view retains the newest 200 packaged rows in this browser and can export
// reviewed records for recognition research. Importing unmatched diagnostics
// is intentional: decoder failures must remain reviewable even when no device
// log row reached this browser.
customElements.whenDefined("esp-app").then(() => {
  const STORAGE_KEY = "esp32.voiceSessions.v1";
  const DIAGNOSTICS_URL_KEY = "esp32.voiceDiagnosticsUrl.v1";
  const MAX_SESSIONS = 200;
  const PAGE_OVERVIEW = "#overview";
  const PAGE_SESSIONS = "#sessions";

  const readSessions = () => {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      return Array.isArray(parsed) ? parsed.slice(0, MAX_SESSIONS) : [];
    } catch (_error) {
      return [];
    }
  };

  const saveSessions = (sessions) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.slice(0, MAX_SESSIONS)));
    } catch (_error) {
      // The live cards still work when browser storage is unavailable.
    }
  };

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const toCsv = (sessions) => {
    const keys = [
      "received_at", "id", "review", "expected_speech", "review_note", "wake", "heard", "reply", "matched",
      "result", "error", "outcome", "ok", "one_breath", "wake_pipeline_ms",
      "replay_ms", "replay_bytes", "wake_speech_ms", "capture_ms", "stt_ms",
      "action_ms", "total_ms", "pre_roll_ms", "rssi_dbm", "wake_sound", "diagnostic_id",
      "decoder_raw_best", "decoder_fuzzy", "decoder_fuzzy_cost", "decoder_score_margin",
      "audio_peak_dbfs", "audio_rms_dbfs", "audio_snr_db", "audio_clipping_percent",
      "audio_tail_active", "audio_issues",
    ];
    const quote = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const flatten = (row) => ({
      ...row,
      diagnostic_id: row.acoustic?.id,
      decoder_raw_best: row.acoustic?.decoder?.raw_best_text,
      decoder_fuzzy: row.acoustic?.decoder?.fuzzy_text,
      decoder_fuzzy_cost: row.acoustic?.decoder?.fuzzy_cost,
      decoder_score_margin: row.acoustic?.decoder?.score_margin,
      audio_peak_dbfs: row.acoustic?.audio?.metrics?.peak_dbfs,
      audio_rms_dbfs: row.acoustic?.audio?.metrics?.rms_dbfs,
      audio_snr_db: row.acoustic?.audio?.metrics?.estimated_snr_db,
      audio_clipping_percent: row.acoustic?.audio?.metrics?.clipping_percent,
      audio_tail_active: row.acoustic?.audio?.metrics?.tail_active,
      audio_issues: (row.acoustic?.audio?.issues || []).join(" | "),
    });
    return [keys.join(","), ...sessions.map(flatten).map((row) => keys.map((key) => quote(row[key])).join(","))].join("\n");
  };

  const download = (name, type, content) => {
    const url = URL.createObjectURL(new Blob([content], {type}));
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const normalizeTranscript = (value) => String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  const recognitionEvidence = (session) => {
    const normalized = normalizeTranscript(session.heard);
    const words = normalized ? normalized.split(" ") : [];
    const onPositions = words.map((word, index) => word === "on" ? index : -1).filter((index) => index >= 0);
    const offPositions = words.map((word, index) => word === "off" ? index : -1).filter((index) => index >= 0);
    let decision = "NO POLARITY TOKEN";
    let evidence = "The final transcript contains neither the word on nor off.";
    if (onPositions.length && offPositions.length) {
      decision = "AMBIGUOUS";
      evidence = `The final transcript contains both on and off at word positions ${onPositions.map((i) => i + 1).join(", ")} and ${offPositions.map((i) => i + 1).join(", ")}.`;
    } else if (offPositions.length) {
      decision = "OFF";
      evidence = `The recognizer returned off as word ${offPositions[0] + 1}; the intent grammar therefore selected the off command.`;
    } else if (onPositions.length) {
      decision = "ON";
      evidence = `The recognizer returned on as word ${onPositions[0] + 1}; the intent grammar therefore selected the on command.`;
    }
    const route = session.outcome?.includes("CUSTOM ACTION")
      ? "Custom Bedroom intent"
      : session.outcome?.includes("GENERIC")
        ? "Generic Home Assistant fallback"
        : session.error
          ? "Pipeline stopped before routing"
          : "No confirmed route";
    return {normalized: normalized || "No transcript", decision, evidence, route};
  };

  const wireSessionHistory = () => {
    const app = document.querySelector("esp-app");
    const root = app?.shadowRoot;
    const header = root?.querySelector("header");
    const overview = root?.querySelector("main");
    const log = root?.querySelector("esp-log");
    const logRoot = log?.shadowRoot;
    const rows = logRoot?.querySelector(".tbody");
    if (!root || !header || !overview || !rows || root.querySelector(".codex-view-tabs")) return;

    const style = document.createElement("style");
    style.textContent = `
      :host { --codex-blue:#38bdf8; --codex-green:#34d399; --codex-amber:#fbbf24; --codex-red:#fb7185; --codex-panel:rgba(15,23,42,.58); --codex-line:rgba(148,163,184,.2); }
      .codex-view-tabs { align-items:center; display:flex; gap:6px; margin:0 auto 18px; max-width:1240px; padding:0 18px; }
      .codex-view-tab { align-items:center; background:rgba(15,23,42,.34); border:1px solid var(--codex-line); border-radius:10px; color:inherit; cursor:pointer; display:flex; font:650 13px system-ui; gap:7px; padding:10px 15px; text-decoration:none; }
      .codex-view-tab.active { background:linear-gradient(135deg,#0284c7,#0369a1); border-color:#38bdf8; box-shadow:0 8px 24px rgba(2,132,199,.2); color:#fff; }
      .codex-tab-report-count { background:rgba(251,191,36,.18); border-radius:999px; color:#fbbf24; font-size:10px; padding:3px 6px; }
      .codex-session-page { margin:0 auto; max-width:1240px; padding:0 18px 40px; }
      .codex-session-page[hidden], main[hidden] { display:none !important; }
      .codex-eyebrow { color:var(--codex-blue); font:750 10px/1.4 ui-monospace,monospace; letter-spacing:.14em; margin-bottom:5px; }
      .codex-session-head { align-items:flex-start; display:flex; flex-wrap:wrap; gap:18px; justify-content:space-between; margin:8px 0 18px; }
      .codex-session-title { font:750 28px/1.15 system-ui; letter-spacing:-.02em; margin:0 0 7px; }
      .codex-session-subtitle { color:rgba(148,163,184,.95); font:13px/1.55 system-ui; max-width:780px; }
      .codex-session-actions { display:flex; flex-wrap:wrap; gap:8px; }
      .codex-session-action { background:rgba(30,41,59,.7); border:1px solid var(--codex-line); border-radius:8px; color:inherit; cursor:pointer; font:650 12px system-ui; padding:9px 12px; }
      .codex-session-action:hover { border-color:rgba(56,189,248,.65); }
      .codex-session-action:disabled { cursor:wait; opacity:.55; }
      .codex-session-list { display:flex; flex-direction:column; gap:8px; }
      .codex-session-row-card { background:var(--codex-panel); border:1px solid var(--codex-line); border-left:3px solid var(--codex-amber); border-radius:11px; overflow:hidden; transition:border-color .15s,background .15s; }
      .codex-session-row-card:hover { border-color:rgba(56,189,248,.4); }
      .codex-session-row-card[open] { background:rgba(15,23,42,.82); border-color:rgba(56,189,248,.48); box-shadow:0 18px 42px rgba(2,6,23,.2); }
      .codex-session-row-card.ok { border-left-color:var(--codex-green); }
      .codex-session-row-card.error { border-left-color:var(--codex-red); }
      .codex-session-summary { align-items:center; cursor:pointer; display:grid; gap:14px; grid-template-columns:170px minmax(180px,1fr) 210px 82px 110px; list-style:none; min-height:48px; padding:12px 16px 12px 44px; position:relative; }
      .codex-session-summary::-webkit-details-marker { display:none; }
      .codex-session-summary::before { content:"+"; font:700 15px ui-monospace,monospace; left:16px; position:absolute; }
      details[open] > .codex-session-summary::before { content:"-"; }
      .codex-summary-heard { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .codex-summary-review { color:#03a9f4; font:700 11px system-ui; text-transform:uppercase; }
      .codex-session-detail { border-top:1px solid var(--codex-line); padding:18px; }
      .codex-detail-grid { display:grid; gap:12px; grid-template-columns:repeat(2,minmax(0,1fr)); }
      .codex-detail-panel { background:rgba(30,41,59,.35); border:1px solid var(--codex-line); border-radius:10px; padding:14px; }
      .codex-detail-panel.full { grid-column:1/-1; }
      .codex-detail-title { align-items:center; display:flex; font:700 12px system-ui; justify-content:space-between; letter-spacing:.04em; margin-bottom:9px; text-transform:uppercase; }
      .codex-session-top { align-items:center; display:flex; gap:8px; justify-content:space-between; }
      .codex-session-id { color:rgba(127,127,127,.95); font:12px ui-monospace,monospace; }
      .codex-session-outcome { font:700 12px system-ui; text-align:right; }
      .codex-session-row { display:grid; font:13px/1.4 system-ui; gap:8px; grid-template-columns:82px 1fr; margin-top:8px; }
      .codex-session-label { color:rgba(127,127,127,.95); font-weight:600; }
      .codex-session-value { overflow-wrap:anywhere; }
      .codex-timing-strip { display:flex; flex-wrap:wrap; gap:6px; margin-top:12px; }
      .codex-timing { background:rgba(127,127,127,.12); border-radius:5px; font:11px ui-monospace,monospace; padding:5px 7px; }
      .codex-recognition-box { background:rgba(14,165,233,.07); border:1px solid rgba(56,189,248,.26); border-radius:10px; margin:0; padding:14px; }
      .codex-recognition-title { font:700 12px system-ui; margin-bottom:8px; text-transform:uppercase; }
      .codex-acoustic-box { background:rgba(16,185,129,.055); border:1px solid rgba(52,211,153,.25); border-radius:10px; margin:0; padding:14px; }
      .codex-candidates { border-collapse:collapse; font:11px ui-monospace,monospace; margin-top:10px; width:100%; }
      .codex-candidates th,.codex-candidates td { border-bottom:1px solid rgba(127,127,127,.2); padding:6px; text-align:left; }
      .codex-acoustic-audio { height:34px; margin-top:10px; max-width:520px; width:100%; }
      .codex-diag-config { align-items:center; background:rgba(15,23,42,.45); border:1px solid var(--codex-line); border-radius:10px; display:flex; flex-wrap:wrap; gap:9px; margin-bottom:14px; padding:12px; }
      .codex-diag-config label { font:600 12px system-ui; }
      .codex-diag-config input { background:rgba(127,127,127,.08); border:1px solid rgba(127,127,127,.3); border-radius:6px; color:inherit; flex:1 1 340px; font:13px system-ui; padding:8px; }
      .codex-diag-status { color:rgba(127,127,127,.95); font:12px system-ui; }
      .codex-protocol-note { color:rgba(127,127,127,.95); font:12px/1.45 system-ui; margin-top:10px; }
      .codex-review { display:flex; flex-wrap:wrap; gap:6px; margin-top:12px; }
      .codex-review button { background:transparent; border:1px solid rgba(127,127,127,.3); border-radius:6px; color:inherit; cursor:pointer; font:11px system-ui; padding:6px 8px; }
      .codex-review button.selected { background:#03a9f4; border-color:#03a9f4; color:#fff; }
      .codex-review-fields { display:grid; gap:8px; grid-template-columns:1fr 1fr; margin-top:10px; }
      .codex-review-fields label { color:rgba(127,127,127,.95); font:600 11px system-ui; }
      .codex-review-fields input { background:rgba(127,127,127,.08); border:1px solid rgba(127,127,127,.3); border-radius:6px; box-sizing:border-box; color:inherit; display:block; font:13px system-ui; margin-top:5px; padding:9px; width:100%; }
      .codex-session-empty { border:1px dashed rgba(127,127,127,.4); border-radius:10px; color:rgba(127,127,127,.95); font:14px/1.5 system-ui; padding:28px; text-align:center; }
      .codex-research-panel { background:linear-gradient(145deg,rgba(8,47,73,.55),rgba(15,23,42,.72)); border:1px solid rgba(56,189,248,.24); border-radius:14px; margin:0 0 24px; padding:17px; }
      .codex-research-head,.codex-list-heading { align-items:center; display:flex; gap:12px; justify-content:space-between; }
      .codex-research-head h3,.codex-list-heading h3 { font:720 18px system-ui; margin:0; }
      .codex-research-state { background:rgba(56,189,248,.12); border:1px solid rgba(56,189,248,.2); border-radius:999px; color:#7dd3fc; font:650 11px system-ui; padding:7px 10px; }
      .codex-research-stats { display:grid; gap:9px; grid-template-columns:repeat(4,1fr); margin:14px 0; }
      .codex-research-stat { background:rgba(2,6,23,.28); border:1px solid var(--codex-line); border-radius:10px; display:grid; padding:11px; }
      .codex-research-stat strong { font:750 22px system-ui; }
      .codex-research-stat span { font:650 11px system-ui; }
      .codex-research-stat small { color:rgba(148,163,184,.9); font:10px system-ui; margin-top:3px; }
      .codex-research-stat.success strong { color:var(--codex-green); } .codex-research-stat.warning strong { color:var(--codex-amber); }
      .codex-capacity-label { color:rgba(203,213,225,.95); display:flex; font:11px system-ui; justify-content:space-between; margin-bottom:6px; }
      .codex-capacity-track { background:rgba(2,6,23,.5); border-radius:999px; height:7px; overflow:hidden; }
      .codex-capacity-track span { background:linear-gradient(90deg,#0284c7,#38bdf8); border-radius:inherit; display:block; height:100%; transition:width .25s; width:0; }
      .codex-capacity-track span.warning { background:linear-gradient(90deg,#d97706,#fbbf24); }
      .codex-report-list { display:grid; gap:9px; margin-top:14px; }
      .codex-report-card { background:rgba(2,6,23,.28); border:1px solid var(--codex-line); border-left:3px solid var(--codex-amber); border-radius:10px; padding:12px; }
      .codex-report-card.analyzed { border-left-color:var(--codex-green); }
      .codex-report-summary,.codex-report-metrics,.codex-report-analysis { align-items:center; display:flex; gap:9px; justify-content:space-between; }
      .codex-report-summary div { display:grid; gap:2px; } .codex-report-summary strong { font:12px ui-monospace,monospace; } .codex-report-summary span { color:rgba(148,163,184,.9); font:10px system-ui; }
      .codex-report-badge { border:1px solid currentColor; border-radius:999px; color:var(--codex-amber) !important; font:650 10px system-ui !important; padding:4px 7px; }
      .codex-report-card.analyzed .codex-report-badge { color:var(--codex-green) !important; }
      .codex-report-metrics { justify-content:flex-start; margin:9px 0; } .codex-report-metrics span { background:rgba(148,163,184,.1); border-radius:5px; font:10px system-ui; padding:5px 7px; }
      .codex-report-card ul { color:rgba(203,213,225,.92); font:11px/1.45 system-ui; margin:7px 0 10px; padding-left:18px; }
      .codex-report-analysis textarea { background:rgba(15,23,42,.72); border:1px solid var(--codex-line); border-radius:7px; color:inherit; flex:1; font:12px/1.4 system-ui; min-height:46px; padding:8px; resize:vertical; }
      .codex-report-buttons { display:flex; flex-direction:column; gap:6px; }
      .codex-report-empty { color:rgba(148,163,184,.95); font:12px/1.45 system-ui; padding:9px 0 2px; }
      .codex-list-heading { margin:0 0 10px; }
      .codex-list-legend { display:flex; gap:12px; } .codex-list-legend span { color:var(--codex-amber); font:600 10px system-ui; } .codex-list-legend .ok { color:var(--codex-green); } .codex-list-legend .error { color:var(--codex-red); }
      .codex-overview-hero { background:radial-gradient(circle at 85% 15%,rgba(14,165,233,.18),transparent 34%),linear-gradient(135deg,rgba(15,23,42,.82),rgba(8,47,73,.65)); border:1px solid rgba(56,189,248,.24); border-radius:16px; display:grid; gap:18px; grid-template-columns:minmax(0,1.4fr) repeat(3,minmax(135px,.55fr)); margin:0 auto 16px; max-width:1204px; padding:20px; }
      .codex-overview-hero[hidden] { display:none; }
      main.codex-overview-main { gap:16px; margin:0 auto !important; max-width:1240px; padding:0 18px 36px !important; }
      main.codex-overview-main > section:first-child { flex:1 1 760px; min-width:0; }
      main.codex-overview-main > section:last-child { flex:1 1 360px; min-width:300px; }
      .codex-hero-status h2 { font:760 29px/1.1 system-ui; letter-spacing:-.025em; margin:3px 0 7px; }
      .codex-hero-status p { color:rgba(148,163,184,.95); font:12px/1.5 system-ui; margin:0; }
      .codex-hero-status.ready h2 { color:var(--codex-green); } .codex-hero-status.busy h2 { color:var(--codex-amber); }
      .codex-hero-metric { align-content:center; background:rgba(2,6,23,.28); border:1px solid var(--codex-line); border-radius:11px; display:grid; gap:5px; padding:12px; }
      .codex-hero-metric span { color:rgba(148,163,184,.9); font:650 10px system-ui; letter-spacing:.06em; text-transform:uppercase; }
      .codex-hero-metric strong { font:650 13px/1.35 system-ui; overflow-wrap:anywhere; }
      @media (max-width:900px) { .codex-session-summary { grid-template-columns:145px minmax(120px,1fr) 90px; } .codex-summary-outcome,.codex-summary-review { display:none; } .codex-detail-grid { grid-template-columns:1fr; } .codex-detail-panel.full { grid-column:auto; } .codex-overview-hero { grid-template-columns:repeat(3,1fr); } .codex-hero-status { grid-column:1/-1; } }
      @media (max-width:600px) { .codex-session-page { padding:0 10px 28px; } .codex-session-summary { grid-template-columns:1fr 70px; } .codex-summary-time,.codex-summary-outcome,.codex-summary-review { display:none; } .codex-session-row { grid-template-columns:70px 1fr; } .codex-review-fields,.codex-research-stats { grid-template-columns:1fr 1fr; } .codex-overview-hero { border-radius:11px; grid-template-columns:1fr; margin:0 10px 14px; padding:15px; } .codex-hero-status { grid-column:auto; } .codex-list-legend { display:none; } .codex-report-analysis { align-items:stretch; flex-direction:column; } .codex-report-buttons { flex-direction:row; } }

      /* Reference-inspired operations console: rail navigation, sharper
         surfaces, oversized readiness type, and master-detail research. */
      :host { --codex-panel:#0c1420; --codex-deep:#071018; --codex-line:rgba(100,116,139,.28); background:radial-gradient(circle at top right,rgba(14,165,233,.08),transparent 30%),var(--codex-deep); color:#f8fafc; min-height:100vh; }
      header { display:none !important; }
      .codex-view-tabs { align-items:stretch; background:rgba(2,8,23,.9); border-right:1px solid var(--codex-line); box-sizing:border-box; flex-direction:column; gap:0; margin:0; max-width:none; min-height:100vh; padding:24px 19px; }
      .codex-sidebar-brand { border-bottom:1px solid var(--codex-line); padding:0 0 22px; }
      .codex-sidebar-kicker { color:#7dd3fc; font:800 11px ui-monospace,monospace; letter-spacing:.3em; text-transform:uppercase; }
      .codex-sidebar-title { color:#fff; font:850 23px/1.1 system-ui; letter-spacing:-.02em; margin-top:9px; }
      .codex-sidebar-subtitle { color:#64748b; font:12px/1.5 system-ui; margin-top:8px; }
      .codex-sidebar-ready { align-items:center; border:1px solid rgba(52,211,153,.35); color:#6ee7b7; display:inline-flex; font:800 10px system-ui; gap:7px; letter-spacing:.14em; margin-top:12px; padding:7px 9px; text-transform:uppercase; }
      .codex-sidebar-ready.busy { border-color:rgba(251,191,36,.35); color:#fbbf24; } .codex-sidebar-ready.error { border-color:rgba(251,113,133,.35); color:#fb7185; }
      .codex-status-dot { background:currentColor; box-shadow:0 0 14px currentColor; display:inline-block; height:8px; width:8px; }
      .codex-sidebar-nav { display:grid; gap:8px; margin-top:26px; }
      .codex-view-tab { border-radius:0; justify-content:space-between; min-height:46px; padding:0 14px; }
      .codex-view-tab small { color:#64748b; font:10px system-ui; }
      .codex-view-tab.active { background:#0ea5e9; border-color:#38bdf8; box-shadow:inset 0 0 0 1px rgba(255,255,255,.25); }
      .codex-view-tab.active small { color:#075985; }
      .codex-sidebar-context { border-top:1px solid var(--codex-line); display:grid; gap:18px; margin-top:28px; padding-top:24px; }
      .codex-sidebar-context h3 { color:#64748b; font:800 10px system-ui; letter-spacing:.2em; margin:0; text-transform:uppercase; }
      .codex-sidebar-fact { display:grid; gap:4px; }
      .codex-sidebar-fact span { color:#64748b; font:750 9px system-ui; letter-spacing:.14em; text-transform:uppercase; }
      .codex-sidebar-fact strong { color:#e2e8f0; font:650 12px/1.4 system-ui; overflow-wrap:anywhere; }
      .codex-session-page { box-sizing:border-box; max-width:1240px; padding:28px 28px 48px; width:100%; }
      .codex-session-title { font:850 38px/1.05 system-ui; letter-spacing:-.035em; margin-bottom:10px; }
      .codex-session-action { border-radius:0; font-weight:800; letter-spacing:.07em; text-transform:uppercase; }
      .codex-diag-config,.codex-research-panel,.codex-research-stat,.codex-report-card,.codex-detail-panel,.codex-recognition-box,.codex-acoustic-box { border-radius:0; }
      .codex-diag-config { margin-bottom:22px; padding:17px; }
      .codex-research-panel { background:rgba(2,6,23,.5); border-color:var(--codex-line); padding:20px; }
      .codex-research-stat,.codex-report-card,.codex-detail-panel { background:var(--codex-panel); }
      .codex-overview-hero { background:rgba(8,47,73,.22); border-radius:0; gap:22px; grid-template-columns:minmax(0,1.35fr) minmax(300px,.65fr); margin-bottom:24px; max-width:1184px; overflow:hidden; padding:30px; position:relative; }
      .codex-overview-hero::after { background:linear-gradient(90deg,#34d399,#38bdf8,#22d3ee); bottom:0; content:""; height:4px; left:0; position:absolute; right:0; }
      .codex-hero-status h2 { font:900 48px/.96 system-ui; letter-spacing:-.045em; margin:14px 0; max-width:700px; }
      .codex-hero-status p { color:#94a3b8; font:14px/1.7 system-ui; max-width:650px; }
      .codex-hero-metrics { display:grid; gap:10px; }
      .codex-hero-metric { background:rgba(2,6,23,.5); border-radius:0; min-height:62px; padding:13px 38px 13px 15px; position:relative; }
      .codex-hero-metric::after { background:var(--codex-blue); box-shadow:0 0 15px var(--codex-blue); content:""; height:10px; position:absolute; right:14px; top:50%; transform:translateY(-50%); width:10px; }
      main.codex-overview-main { gap:22px; max-width:1240px; padding:0 28px 48px !important; }
      main.codex-overview-main { display:grid !important; grid-template-columns:minmax(0,1fr); }
      main.codex-overview-main[hidden] { display:none !important; }
      main.codex-overview-main > section { min-width:0 !important; overflow:hidden; }
      .codex-research-workspace { align-items:start; display:grid; gap:22px; grid-template-columns:310px minmax(0,1fr); }
      .codex-session-queue { display:grid; gap:8px; position:sticky; top:24px; }
      .codex-session-choice { background:rgba(2,6,23,.48); border:1px solid var(--codex-line); color:inherit; cursor:pointer; display:grid; gap:7px; padding:14px; text-align:left; }
      .codex-session-choice:hover,.codex-session-choice.active { background:rgba(8,47,73,.42); border-color:#38bdf8; }
      .codex-session-choice-top { align-items:center; display:flex; gap:8px; justify-content:space-between; }
      .codex-session-choice-heard { color:#fff; font:750 13px/1.35 system-ui; overflow-wrap:anywhere; }
      .codex-session-choice-meta { color:#64748b; font:10px/1.35 ui-monospace,monospace; }
      .codex-session-choice-state { color:var(--codex-amber); font:800 9px system-ui; letter-spacing:.08em; text-transform:uppercase; }
      .codex-session-choice.ok .codex-session-choice-state { color:var(--codex-green); } .codex-session-choice.error .codex-session-choice-state { color:var(--codex-red); }
      .codex-selected-session { min-width:0; }
      .codex-selected-hero { background:linear-gradient(135deg,rgba(16,185,129,.11),rgba(14,165,233,.06),rgba(2,6,23,.68)); border:1px solid rgba(52,211,153,.28); margin-bottom:14px; padding:20px; }
      .codex-selected-hero h3 { color:#fff; font:850 30px/1.1 system-ui; letter-spacing:-.025em; margin:12px 0 7px; }
      .codex-selected-hero p { color:#94a3b8; font:12px/1.55 system-ui; margin:0; }
      @media (min-width:1001px) { :host { display:grid; grid-template-columns:282px minmax(0,1fr); } .codex-view-tabs { grid-column:1; grid-row:1/20; height:100vh; position:sticky; top:0; } .codex-session-page,main.codex-overview-main,.codex-overview-hero { grid-column:2; } }
      @media (max-width:1000px) { .codex-view-tabs { border-bottom:1px solid var(--codex-line); border-right:0; min-height:0; padding:16px; } .codex-sidebar-brand { align-items:center; display:flex; gap:14px; justify-content:space-between; padding-bottom:14px; } .codex-sidebar-title { font-size:18px; margin-top:3px; } .codex-sidebar-subtitle,.codex-sidebar-context { display:none; } .codex-sidebar-ready { margin-top:0; } .codex-sidebar-nav { grid-template-columns:1fr 1fr; margin-top:14px; } .codex-overview-hero { grid-template-columns:1fr; margin:0 18px 22px; } .codex-hero-metrics { grid-template-columns:repeat(3,1fr); } main.codex-overview-main { grid-template-columns:1fr; } }
      @media (max-width:760px) { .codex-research-workspace { grid-template-columns:1fr; } .codex-session-queue { grid-auto-columns:minmax(230px,80%); grid-auto-flow:column; overflow-x:auto; position:static; } }
      @media (max-width:600px) { .codex-session-page { padding:22px 10px 28px; } .codex-session-title { font-size:32px; } .codex-overview-hero { grid-template-columns:1fr; margin:0 10px 18px; padding:20px 17px; } .codex-hero-status h2 { font-size:38px; } .codex-hero-metrics { grid-template-columns:1fr; } main.codex-overview-main { padding:0 10px 32px !important; } }

      /* Purpose-built voice console. The stock entity table remains alive as
         the ESPHome transport/fallback surface, but is no longer the UI. */
      :host { --voice-ink:#eef7f4; --voice-muted:#8da5a0; --voice-card:#0b171b; --voice-card-2:#0f2024; --voice-green:#48e1a4; --voice-mint:#9af4d0; --voice-coral:#ff8c6b; --voice-yellow:#f7c85d; background:radial-gradient(circle at 78% 4%,rgba(72,225,164,.10),transparent 32%),#061014; }
      main.codex-overview-main { display:none !important; }
      .codex-overview-hero { background:none; border:0; display:block; margin:0; max-width:none; overflow:visible; padding:28px 30px 54px; }
      .codex-overview-hero::after { display:none; }
      .voice-console { margin:0 auto; max-width:1180px; }
      .voice-console-top { align-items:center; display:flex; gap:18px; justify-content:space-between; margin-bottom:26px; }
      .voice-console-title { color:var(--voice-ink); font:850 clamp(27px,3vw,42px)/1 system-ui; letter-spacing:-.045em; margin:0; }
      .voice-console-title span { color:var(--voice-green); }
      .voice-console-meta { color:var(--voice-muted); font:650 12px/1.4 ui-monospace,monospace; margin-top:8px; }
      .voice-live-pill { align-items:center; background:rgba(72,225,164,.08); border:1px solid rgba(72,225,164,.26); border-radius:999px; color:var(--voice-mint); display:flex; font:800 12px system-ui; gap:9px; padding:10px 15px; }
      .voice-live-pill::before { background:currentColor; border-radius:50%; box-shadow:0 0 0 5px rgba(72,225,164,.10),0 0 18px currentColor; content:""; height:8px; width:8px; }
      .voice-live-pill.busy { background:rgba(247,200,93,.08); border-color:rgba(247,200,93,.30); color:var(--voice-yellow); }
      .voice-live-pill.error { background:rgba(255,140,107,.08); border-color:rgba(255,140,107,.32); color:var(--voice-coral); }
      .voice-primary-grid { display:grid; gap:18px; grid-template-columns:minmax(0,1.34fr) minmax(330px,.66fr); }
      .voice-card { background:linear-gradient(145deg,rgba(15,32,36,.98),rgba(9,22,26,.98)); border:1px solid rgba(141,165,160,.16); border-radius:24px; box-shadow:0 22px 60px rgba(0,0,0,.22); box-sizing:border-box; }
      .voice-presence { align-items:center; display:grid; gap:26px; grid-template-columns:154px minmax(0,1fr); min-height:322px; overflow:hidden; padding:32px; position:relative; }
      .voice-presence::after { background:radial-gradient(circle,rgba(72,225,164,.12),transparent 68%); content:""; height:320px; pointer-events:none; position:absolute; right:-110px; top:-130px; width:320px; }
      .voice-orb { align-items:center; aspect-ratio:1; background:radial-gradient(circle at 36% 32%,#9af4d0 0 8%,#48e1a4 9% 25%,#168a68 56%,#0c4539 100%); border:1px solid rgba(154,244,208,.55); border-radius:50%; box-shadow:0 0 0 12px rgba(72,225,164,.05),0 0 0 25px rgba(72,225,164,.025),0 28px 70px rgba(32,210,149,.25); display:flex; justify-content:center; position:relative; transition:filter .25s,transform .25s; }
      .voice-orb::before { border:2px solid rgba(6,32,24,.45); border-radius:50%; content:""; inset:24%; position:absolute; }
      .voice-orb::after { background:#062018; border-radius:50%; box-shadow:0 0 22px rgba(6,32,24,.55); content:""; height:18%; position:absolute; width:18%; }
      .voice-orb.busy { animation:voice-breathe 1.7s ease-in-out infinite; filter:hue-rotate(72deg); }
      .voice-orb.error { filter:hue-rotate(140deg) saturate(.78); }
      @keyframes voice-breathe { 50% { box-shadow:0 0 0 18px rgba(247,200,93,.06),0 0 0 36px rgba(247,200,93,.025),0 28px 80px rgba(247,200,93,.22); transform:scale(1.025); } }
      @media (prefers-reduced-motion:reduce) { .voice-orb.busy { animation:none; } * { scroll-behavior:auto !important; transition-duration:.01ms !important; } }
      .voice-kicker { color:var(--voice-green); font:850 11px/1.4 ui-monospace,monospace; letter-spacing:.18em; text-transform:uppercase; }
      .voice-state-title { color:var(--voice-ink); font:900 clamp(35px,5vw,62px)/.96 system-ui; letter-spacing:-.055em; margin:12px 0 14px; }
      .voice-state-copy { color:var(--voice-muted); font:16px/1.6 system-ui; margin:0; max-width:570px; }
      .voice-wake-phrase { align-items:center; background:rgba(72,225,164,.07); border:1px solid rgba(72,225,164,.16); border-radius:14px; color:#c9f9e7; display:inline-flex; font:750 14px system-ui; gap:9px; margin-top:24px; padding:11px 14px; }
      .voice-wake-phrase span { color:var(--voice-green); }
      .voice-volume { display:flex; flex-direction:column; min-height:322px; padding:28px; }
      .voice-card-head { align-items:flex-start; display:flex; gap:16px; justify-content:space-between; }
      .voice-card-label { color:var(--voice-muted); font:800 12px/1.4 system-ui; letter-spacing:.08em; text-transform:uppercase; }
      .voice-volume-number { color:var(--voice-ink); font:900 58px/.9 system-ui; letter-spacing:-.06em; }
      .voice-volume-number small { color:var(--voice-muted); font-size:18px; letter-spacing:0; }
      .voice-range-wrap { margin:38px 0 22px; }
      .voice-range { accent-color:var(--voice-green); cursor:pointer; height:34px; margin:0; width:100%; }
      .voice-range-labels { color:var(--voice-muted); display:flex; font:700 11px ui-monospace,monospace; justify-content:space-between; margin-top:3px; }
      .voice-volume-actions { display:grid; gap:10px; grid-template-columns:52px 1fr 52px; margin-top:auto; }
      .voice-button { align-items:center; background:#14282d; border:1px solid rgba(141,165,160,.22); border-radius:14px; color:var(--voice-ink); cursor:pointer; display:inline-flex; font:800 14px system-ui; justify-content:center; min-height:48px; padding:0 16px; transition:background .15s,border-color .15s,transform .15s; }
      .voice-button:hover { background:#193239; border-color:rgba(72,225,164,.42); }
      .voice-button:active { transform:scale(.98); }
      .voice-button:focus-visible,.voice-switch:focus-visible,.voice-range:focus-visible { outline:3px solid rgba(72,225,164,.55); outline-offset:3px; }
      .voice-button.primary { background:var(--voice-green); border-color:var(--voice-green); color:#062018; }
      .voice-button.primary:hover { background:var(--voice-mint); }
      .voice-button.warning { color:#ffd8cc; }
      .voice-button:disabled { cursor:wait; opacity:.55; }
      .voice-secondary-grid { display:grid; gap:18px; grid-template-columns:repeat(2,minmax(0,1fr)); margin-top:18px; }
      .voice-section { padding:25px; }
      .voice-section-title { color:var(--voice-ink); font:850 20px/1.2 system-ui; letter-spacing:-.02em; margin:5px 0 20px; }
      .voice-toggle-list { display:grid; gap:10px; }
      .voice-toggle-row { align-items:center; background:rgba(4,13,16,.34); border:1px solid rgba(141,165,160,.13); border-radius:16px; display:flex; gap:16px; justify-content:space-between; min-height:68px; padding:10px 12px 10px 16px; }
      .voice-toggle-copy { display:grid; gap:4px; }
      .voice-toggle-copy strong { color:var(--voice-ink); font:780 15px system-ui; }
      .voice-toggle-copy span { color:var(--voice-muted); font:13px/1.35 system-ui; }
      .voice-switch { background:#24383d; border:0; border-radius:999px; cursor:pointer; height:34px; padding:3px; position:relative; transition:background .2s; width:58px; }
      .voice-switch::after { background:#8da5a0; border-radius:50%; box-shadow:0 3px 8px rgba(0,0,0,.28); content:""; display:block; height:28px; transition:background .2s,transform .2s; width:28px; }
      .voice-switch[aria-pressed="true"] { background:rgba(72,225,164,.24); }
      .voice-switch[aria-pressed="true"]::after { background:var(--voice-green); transform:translateX(24px); }
      .voice-conversation { display:grid; gap:12px; }
      .voice-bubble { background:rgba(4,13,16,.42); border:1px solid rgba(141,165,160,.13); border-radius:16px 16px 16px 5px; padding:15px 17px; }
      .voice-bubble.reply { background:rgba(72,225,164,.07); border-color:rgba(72,225,164,.17); border-radius:16px 16px 5px 16px; }
      .voice-bubble span { color:var(--voice-muted); display:block; font:800 10px ui-monospace,monospace; letter-spacing:.12em; margin-bottom:7px; text-transform:uppercase; }
      .voice-bubble strong { color:var(--voice-ink); font:700 15px/1.5 system-ui; overflow-wrap:anywhere; }
      .voice-stats { display:grid; gap:10px; grid-template-columns:repeat(4,1fr); margin-top:18px; }
      .voice-stat { background:rgba(4,13,16,.38); border:1px solid rgba(141,165,160,.13); border-radius:16px; padding:16px; }
      .voice-stat span { color:var(--voice-muted); display:block; font:750 10px/1.3 system-ui; letter-spacing:.07em; margin-bottom:8px; text-transform:uppercase; }
      .voice-stat strong { color:var(--voice-ink); font:800 17px/1.2 ui-monospace,monospace; overflow-wrap:anywhere; }
      .voice-tools { align-items:center; display:flex; flex-wrap:wrap; gap:10px; margin-top:18px; }
      .voice-tools-note { color:var(--voice-muted); flex:1 1 260px; font:13px/1.5 system-ui; }
      .voice-toast { background:#d9fff0; border-radius:12px; bottom:22px; box-shadow:0 14px 45px rgba(0,0,0,.35); color:#08251c; font:800 13px system-ui; opacity:0; padding:12px 16px; pointer-events:none; position:fixed; right:22px; transform:translateY(10px); transition:opacity .2s,transform .2s; z-index:50; }
      .voice-toast.show { opacity:1; transform:translateY(0); }

      /* Voice Lab evidence inbox. Outcome flags and human-review state are
         intentionally separate so color never has to carry meaning alone. */
      .codex-session-page { color:var(--voice-ink); max-width:1260px; padding:30px 30px 54px; }
      .codex-session-head { align-items:flex-end; border-bottom:1px solid rgba(141,165,160,.14); margin-bottom:22px; padding-bottom:24px; }
      .codex-session-title { color:var(--voice-ink); font:850 clamp(34px,4vw,52px)/.98 system-ui; letter-spacing:-.045em; margin:7px 0 12px; }
      .codex-session-subtitle { color:var(--voice-muted); font:14px/1.65 system-ui; max-width:760px; }
      .codex-session-actions { align-items:center; display:flex; flex-wrap:wrap; gap:8px; justify-content:flex-end; }
      .codex-session-action { background:rgba(141,165,160,.07); border:1px solid rgba(141,165,160,.22); border-radius:12px; color:var(--voice-ink); cursor:pointer; font:750 11px system-ui; letter-spacing:.04em; min-height:40px; padding:0 13px; text-transform:none; }
      .codex-session-action:hover { background:rgba(72,225,164,.09); border-color:rgba(72,225,164,.42); }
      .voice-lab-guide { align-items:center; background:linear-gradient(135deg,rgba(15,32,36,.98),rgba(8,22,25,.98)); border:1px solid rgba(141,165,160,.16); border-radius:18px; display:flex; flex-wrap:wrap; gap:13px 20px; margin-bottom:16px; padding:15px 18px; }
      .voice-lab-guide strong { color:var(--voice-ink); font:800 12px system-ui; margin-right:auto; }
      .voice-lab-key { align-items:center; color:var(--voice-muted); display:inline-flex; font:650 11px system-ui; gap:7px; }
      .evidence-result-flag { align-items:center; border:1px solid currentColor; border-radius:999px; display:inline-flex; flex:0 0 auto; font:850 10px system-ui; gap:6px; letter-spacing:.035em; padding:5px 8px; }
      .evidence-result-flag::before { content:""; display:block; height:6px; width:6px; }
      .evidence-result-flag.success { background:rgba(72,225,164,.09); color:var(--voice-green); }
      .evidence-result-flag.success::before { background:currentColor; border-radius:50%; box-shadow:0 0 10px currentColor; }
      .evidence-result-flag.error { background:rgba(255,140,107,.09); color:var(--voice-coral); }
      .evidence-result-flag.error::before { background:currentColor; transform:rotate(45deg); }
      .evidence-result-flag.captured { background:rgba(141,165,160,.07); color:#a8bfba; }
      .evidence-result-flag.captured::before { border:1px solid currentColor; border-radius:50%; box-sizing:border-box; }
      .evidence-review-dot { background:#38bdf8; border-radius:50%; box-shadow:0 0 0 4px rgba(56,189,248,.11),0 0 14px rgba(56,189,248,.75); display:inline-block; flex:0 0 auto; height:8px; width:8px; }
      .voice-lab-inbox-stats { display:grid; gap:10px; grid-template-columns:repeat(4,1fr); margin-bottom:22px; }
      .voice-lab-inbox-stat { background:var(--voice-card); border:1px solid rgba(141,165,160,.16); border-radius:16px; display:grid; gap:4px; padding:16px 17px; }
      .voice-lab-inbox-stat strong { color:var(--voice-ink); font:850 27px/1 system-ui; }
      .voice-lab-inbox-stat span { color:var(--voice-muted); font:700 11px system-ui; }
      .voice-lab-inbox-stat.needs-review strong { color:#7dd3fc; }
      .voice-lab-inbox-stat.success strong { color:var(--voice-green); }
      .voice-lab-inbox-stat.error strong { color:var(--voice-coral); }
      .codex-diag-config { background:rgba(15,32,36,.72); border:1px solid rgba(141,165,160,.16); border-radius:16px; margin-bottom:24px; padding:13px 15px; }
      .codex-diag-config input { border-radius:10px; min-height:38px; }
      .codex-list-heading { align-items:flex-end; margin:0 0 13px; }
      .codex-list-heading h3 { color:var(--voice-ink); font:820 23px system-ui; }
      .codex-list-legend { color:var(--voice-muted); font:600 11px/1.4 system-ui; }
      .codex-research-workspace { gap:18px; grid-template-columns:minmax(280px,340px) minmax(0,1fr); }
      .codex-session-queue { gap:9px; max-height:calc(100vh - 48px); overflow:auto; padding-right:4px; }
      .codex-session-choice { background:rgba(11,23,27,.88); border:1px solid rgba(141,165,160,.15); border-radius:16px; gap:9px; min-height:112px; padding:15px 16px; position:relative; }
      .codex-session-choice:hover { background:rgba(15,32,36,.98); border-color:rgba(141,165,160,.38); }
      .codex-session-choice.active { background:linear-gradient(145deg,rgba(15,43,46,.98),rgba(10,26,30,.98)); border-color:rgba(72,225,164,.52); box-shadow:inset 3px 0 0 var(--voice-green); }
      .codex-session-choice-top { align-items:flex-start; }
      .codex-session-choice-heard { font:780 14px/1.4 system-ui; padding-right:4px; }
      .codex-session-choice-badges { align-items:center; display:flex; gap:10px; }
      .codex-session-choice-meta { color:#718b86; font:10px/1.45 ui-monospace,monospace; }
      .codex-selected-session { background:rgba(7,17,20,.54); border:1px solid rgba(141,165,160,.14); border-radius:22px; overflow:hidden; }
      .codex-selected-hero { background:radial-gradient(circle at 90% 10%,rgba(72,225,164,.11),transparent 33%),linear-gradient(145deg,rgba(15,32,36,.98),rgba(9,22,26,.98)); border:0; border-bottom:1px solid rgba(141,165,160,.14); margin:0; padding:25px 26px; }
      .codex-selected-session.error .codex-selected-hero { background:radial-gradient(circle at 90% 10%,rgba(255,140,107,.12),transparent 33%),linear-gradient(145deg,rgba(15,32,36,.98),rgba(9,22,26,.98)); }
      .codex-selected-hero h3 { font:850 clamp(25px,3vw,36px)/1.12 system-ui; margin:18px 0 9px; }
      .codex-selected-hero p { color:var(--voice-muted); font:13px/1.6 system-ui; }
      .voice-selected-status { align-items:center; display:flex; flex-wrap:wrap; gap:11px; }
      .voice-review-state { align-items:center; color:#7dd3fc; display:inline-flex; font:750 11px system-ui; gap:9px; }
      .voice-review-state.reviewed { color:var(--voice-muted); }
      .codex-detail-grid { gap:12px; padding:14px; }
      .codex-detail-panel,.codex-recognition-box,.codex-acoustic-box { background:var(--voice-card); border:1px solid rgba(141,165,160,.15); border-radius:15px; }
      .codex-review button { border-radius:10px; min-height:38px; padding:7px 11px; }
      .codex-review button.selected { background:var(--voice-green); border-color:var(--voice-green); color:#062017; }
      .codex-research-panel { background:rgba(11,23,27,.78); border:1px solid rgba(141,165,160,.15); border-radius:20px; margin:30px 0 0; padding:20px; }
      .codex-research-stat,.codex-report-card { border-radius:13px; }
      @media (max-width:900px) { .voice-primary-grid { grid-template-columns:1fr; } .voice-volume { min-height:280px; } .voice-presence { min-height:290px; } .voice-stats { grid-template-columns:repeat(2,1fr); } }
      @media (max-width:760px) { .voice-lab-inbox-stats { grid-template-columns:1fr 1fr; } .codex-research-workspace { grid-template-columns:1fr; } .codex-session-queue { grid-auto-columns:minmax(260px,82%); max-height:none; overflow-x:auto; } }
      @media (max-width:650px) { .codex-overview-hero { padding:20px 12px 36px; } .voice-console-top { align-items:flex-start; } .voice-live-pill { padding:9px 11px; } .voice-primary-grid,.voice-secondary-grid { grid-template-columns:1fr; } .voice-presence { grid-template-columns:86px minmax(0,1fr); min-height:0; padding:24px 20px; } .voice-state-title { font-size:36px; } .voice-state-copy { font-size:14px; } .voice-wake-phrase { margin-top:17px; } .voice-volume,.voice-section { padding:21px; } .voice-stats { grid-template-columns:1fr 1fr; } .voice-button { min-height:50px; } .voice-tools { align-items:stretch; flex-direction:column; } .voice-tools .voice-button { width:100%; } .codex-session-page { padding:22px 12px 36px; } .codex-session-head { align-items:flex-start; } .codex-session-actions { justify-content:flex-start; } .voice-lab-guide { align-items:flex-start; flex-direction:column; } .voice-lab-guide strong { margin-right:0; } .codex-research-stats { grid-template-columns:1fr 1fr; } .codex-detail-grid { grid-template-columns:1fr; padding:10px; } }
    `;
    root.appendChild(style);

    const tabs = document.createElement("aside");
    tabs.className = "codex-view-tabs";
    tabs.innerHTML = `
      <div class="codex-sidebar-brand"><div><div class="codex-sidebar-kicker">ESP32-S3</div><div class="codex-sidebar-title">Voice Satellite</div><div class="codex-sidebar-subtitle">Private, local voice control</div></div><div class="codex-sidebar-ready" data-sidebar-ready><span class="codex-status-dot"></span><span data-sidebar-ready-text>Connecting</span></div></div>
      <nav class="codex-sidebar-nav" aria-label="Primary navigation">
        <a class="codex-view-tab" href="${PAGE_OVERVIEW}" data-view="overview"><span>Control</span><small>Live device</small></a>
        <a class="codex-view-tab" href="${PAGE_SESSIONS}" data-view="sessions"><span>Voice Lab <span data-session-count>0</span></span><small data-sidebar-report-meta>Evidence</small><span class="codex-tab-report-count" data-report-count hidden></span></a>
      </nav>
      <div class="codex-sidebar-context"><h3 data-sidebar-workspace>Live operations</h3><div class="codex-sidebar-fact"><span>Last heard</span><strong data-sidebar-heard>No transcript yet</strong></div><div class="codex-sidebar-fact"><span>Assistant reply</span><strong data-sidebar-reply>No reply yet</strong></div><div class="codex-sidebar-fact"><span>Last request</span><strong data-sidebar-timing>Waiting for timing</strong></div></div>
    `;
    header.insertAdjacentElement("afterend", tabs);

    const page = document.createElement("section");
    page.className = "codex-session-page";
    page.hidden = true;
    page.innerHTML = `
      <div class="codex-session-head">
        <div><div class="codex-eyebrow">VOICE LAB</div><h2 class="codex-session-title">Evidence inbox</h2><div class="codex-session-subtitle">Inspect every voice request, confirm what worked, and label problems for the next research report. Device outcome and human review are tracked separately.</div></div>
        <div class="codex-session-actions"><button class="codex-session-action" data-export="json">Export JSON</button><button class="codex-session-action" data-export="csv">Export CSV</button><button class="codex-session-action" data-clear>Clear local history</button></div>
      </div>
      <div class="voice-lab-guide" aria-label="Evidence status guide"><strong>How to read each record</strong><span class="voice-lab-key"><span class="evidence-result-flag success">Successful</span>request completed</span><span class="voice-lab-key"><span class="evidence-result-flag error">Error</span>failure recorded</span><span class="voice-lab-key"><span class="evidence-review-dot" aria-hidden="true"></span>needs your review; the dot disappears after review</span></div>
      <div class="voice-lab-inbox-stats" data-inbox-stats></div>
      <div class="codex-diag-config"><label for="codex-diag-url">Acoustic diagnostics service</label><input id="codex-diag-url" data-diagnostics-url placeholder="http://homeassistant.local:11400"><button class="codex-session-action" type="button" data-diagnostics-connect>Connect</button><span class="codex-diag-status" data-diagnostics-status>Not configured</span></div>
      <div class="codex-list-heading"><div><div class="codex-eyebrow">LATEST EVIDENCE</div><h3>Review queue</h3></div><div class="codex-list-legend">Select a record to inspect its transcript, audio, timing, and review controls.</div></div>
      <div class="codex-session-list"></div>
      <section class="codex-research-panel">
        <div class="codex-research-head"><div><div class="codex-eyebrow">AUTORESEARCH RETENTION</div><h3>Evidence archive</h3></div><div class="codex-research-state" data-research-state>Waiting for diagnostics</div></div>
        <div class="codex-research-stats" data-research-stats></div>
        <div class="codex-capacity"><div class="codex-capacity-label"><span>Raw evidence capacity</span><span data-capacity-label>0%</span></div><div class="codex-capacity-track"><span data-capacity-fill></span></div></div>
        <div class="codex-report-list" data-report-list><div class="codex-report-empty">No completed research reports yet.</div></div>
      </section>
    `;
    overview.insertAdjacentElement("afterend", page);

    overview.classList.add("codex-overview-main");
    const hero = document.createElement("section");
    hero.className = "codex-overview-hero";
    hero.innerHTML = `
      <div class="voice-console">
        <header class="voice-console-top"><div><h1 class="voice-console-title">Voice <span>Satellite</span></h1><div class="voice-console-meta">ESP32-S3 · LOCAL CONTROL</div></div><div class="voice-live-pill" data-live-pill>Connecting</div></header>
        <div class="voice-primary-grid">
          <section class="voice-card voice-presence" aria-live="polite">
            <div class="voice-orb" data-voice-orb aria-hidden="true"></div>
            <div><div class="voice-kicker" data-voice-kicker>Checking voice pipeline</div><h2 class="voice-state-title" data-voice-title>Connecting…</h2><p class="voice-state-copy" data-voice-copy>Waiting for the assistant to report its current state.</p><div class="voice-wake-phrase">Say <span>“Hey Burden”</span></div></div>
          </section>
          <section class="voice-card voice-volume">
            <div class="voice-card-head"><div><div class="voice-card-label">Speaker volume</div><div class="voice-console-meta">Full digital output range</div></div><div class="voice-volume-number"><span data-volume-value>--</span><small>%</small></div></div>
            <div class="voice-range-wrap"><input class="voice-range" data-volume-range type="range" min="0" max="100" step="5" value="50" aria-label="Speaker volume"><div class="voice-range-labels"><span>Muted 0%</span><span>Full 100%</span></div></div>
            <div class="voice-volume-actions"><button class="voice-button" type="button" data-volume-step="-5" aria-label="Lower volume">−</button><button class="voice-button primary" type="button" data-device-button="Test Speaker">Test speaker</button><button class="voice-button" type="button" data-volume-step="5" aria-label="Raise volume">+</button></div>
          </section>
        </div>
        <section class="voice-card voice-section" style="margin-bottom:20px">
          <div class="voice-kicker">Listen and compare</div><h2 class="voice-section-title">Speaker sound tests</h2>
          <p class="voice-tools-note">Plays through the ESP32 speaker at the volume above. Speech samples are stored on the board. Tests pause wake-word listening and switch the ring off until playback finishes.</p>
          <div style="display:flex;flex-wrap:wrap;gap:10px;margin:16px 0">
            <button class="voice-button" data-device-button="Test Speaker">Frequency sweep</button>
            <button class="voice-button" data-device-button="Test Chime">Doorbell chime</button>
            <button class="voice-button" data-device-button="Test Random Sound">Random melody</button>
            <button class="voice-button" data-device-button="Test Soft Noise">Soft noise</button>
            <button class="voice-button" data-device-button="Test Level Steps">Rising level test</button>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:10px;margin:16px 0">
            <button class="voice-button primary" data-device-button="Test Speech A">Speech: counting</button>
            <button class="voice-button primary" data-device-button="Test Speech B">Speech: lights</button>
            <button class="voice-button" data-device-button="Test Speech Stereo">Counting: stereo comparison</button>
            <button class="voice-button warning" data-device-button="Stop Test Sound">Stop test</button>
          </div>
          <p class="voice-tools-note">The rising test plays four 1 kHz tones at 10%, 25%, 50%, and 80% source amplitude. Counting and its stereo comparison use identical speech and levels. Start low and compare clarity as you raise the main volume.</p>
        </section>
        <div class="voice-secondary-grid">
          <section class="voice-card voice-section"><div class="voice-kicker">Everyday controls</div><h2 class="voice-section-title">Listening preferences</h2><div class="voice-toggle-list">
            <div class="voice-toggle-row"><div class="voice-toggle-copy"><strong>Wake word</strong><span>Listen for “Hey Burden”</span></div><button class="voice-switch" type="button" data-device-switch="Wake Word Enabled" aria-label="Toggle wake word" aria-pressed="false"></button></div>
            <div class="voice-toggle-row"><div class="voice-toggle-copy"><strong>Wake sound</strong><span>Play a short acknowledgement</span></div><button class="voice-switch" type="button" data-device-switch="Wake Sound" aria-label="Toggle wake sound" aria-pressed="false"></button></div>
            <div class="voice-toggle-row"><div class="voice-toggle-copy"><strong>One-breath buffer</strong><span>How much speech to retain before the command</span></div><div><input class="voice-range" data-preroll-range type="range" min="180" max="340" step="20" value="260" aria-label="One-breath pre-roll"><div class="voice-range-labels"><span>180 ms</span><strong data-preroll-value>-- ms</strong><span>340 ms</span></div></div></div>
          </div></section>
          <section class="voice-card voice-section"><div class="voice-kicker">Latest interaction</div><h2 class="voice-section-title">What just happened</h2><div class="voice-conversation"><div class="voice-bubble"><span>You said</span><strong data-last-heard>Nothing heard yet</strong></div><div class="voice-bubble reply"><span>Assistant</span><strong data-last-reply>No reply yet</strong></div></div></section>
        </div>
        <div class="voice-stats" aria-label="Device health"><div class="voice-stat"><span>Pipeline</span><strong data-stat-pipeline>Waiting</strong></div><div class="voice-stat"><span>Total time</span><strong data-stat-time>—</strong></div><div class="voice-stat"><span>Wi-Fi</span><strong data-stat-wifi>—</strong></div><div class="voice-stat"><span>Free memory</span><strong data-stat-memory>—</strong></div></div>
        <section class="voice-card voice-section voice-tools"><div class="voice-tools-note"><strong style="color:var(--voice-ink)">Device tools</strong><br>Restart controls are intentionally separated from everyday actions.</div><button class="voice-button warning" type="button" data-device-button="Restart Device" data-confirm="Restart the voice satellite now?">Restart device</button><button class="voice-button warning" type="button" data-device-button="Restart in Safe Mode" data-confirm="Restart the voice satellite in safe mode?">Safe mode</button></section>
      </div><div class="voice-toast" data-voice-toast role="status"></div>`;
    overview.insertAdjacentElement("beforebegin", hero);

    const entityTableRoot = overview.querySelector("esp-entity-table")?.shadowRoot;
    if (entityTableRoot && !entityTableRoot.querySelector("[data-codex-overview-style]")) {
      const entityStyle = document.createElement("style");
      entityStyle.dataset.codexOverviewStyle = "true";
      entityStyle.textContent = `
        :host { --codex-line:rgba(148,163,184,.2); }
        .tab-header { color:#7dd3fc; font:750 11px system-ui; letter-spacing:.11em; margin:16px 0 7px; padding:0 3px; text-transform:uppercase; }
        .tab-header:first-child { margin-top:0; }
        .tab-container { background:#0c1420; border:1px solid var(--codex-line); border-radius:0; display:grid; gap:0 16px; grid-template-columns:repeat(2,minmax(0,1fr)); overflow:hidden; padding:4px 12px; }
        .entity-row { border-bottom:1px solid rgba(148,163,184,.12); min-height:47px; }
        .entity-row > div:nth-child(2) { color:rgba(203,213,225,.9); font-size:12px; }
        .entity-row > div:last-child { font-weight:650; overflow-wrap:anywhere; text-align:right; }
        @media (max-width:700px) { .tab-container { grid-template-columns:1fr; } }
      `;
      entityTableRoot.appendChild(entityStyle);
    }

    const deviceValues = {};
    let toastTimer;
    const showToast = (message) => {
      const toast = hero.querySelector("[data-voice-toast]");
      toast.textContent = message;
      toast.classList.add("show");
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toast.classList.remove("show"), 2200);
    };
    const friendlyVoiceState = (availability, voiceState) => {
      const combined = `${availability} ${voiceState}`.toUpperCase();
      if (combined.includes("ERROR") || combined.includes("UNAVAILABLE")) return {kind:"error", kicker:"Needs attention", title:"Unavailable", copy:voiceState || availability};
      if (combined.includes("SPEAKING") || combined.includes("RESPONSE")) return {kind:"busy", kicker:"Assistant response", title:"Speaking", copy:"The assistant is playing its response."};
      if (combined.includes("PROCESS") || combined.includes("STT") || combined.includes("THINK")) return {kind:"busy", kicker:"Processing your request", title:"Thinking", copy:"Your request is being recognized and routed."};
      if (combined.includes("LISTEN") && !combined.includes("WAITING")) return {kind:"busy", kicker:"Microphone active", title:"Listening", copy:"Speak naturally. The assistant is capturing your request."};
      if (combined.includes("READY") || combined.includes("WAITING FOR WAKE")) return {kind:"ready", kicker:"Ready for a request", title:"Ready for you", copy:"The microphone is listening locally for the wake phrase."};
      return {kind:"busy", kicker:"Voice pipeline active", title:"Working", copy:voiceState || availability || "Waiting for the device."};
    };
    const updateHero = () => {
      const tableRoot = overview.querySelector("esp-entity-table")?.shadowRoot;
      if (!tableRoot) return;
      const values = {};
      tableRoot.querySelectorAll(".entity-row").forEach((row) => {
        const cells = row.children;
        const label = cells[1]?.textContent?.trim();
        if (label) {
          const control = cells[2]?.querySelector?.("input[type=checkbox]") || cells[2]?.querySelector?.("esp-switch")?.shadowRoot?.querySelector("input[type=checkbox]");
          values[label] = control ? (control.checked ? "Enabled" : "Disabled") : (cells[2]?.textContent?.trim() || "");
        }
      });
      Object.assign(deviceValues, values);
      const availability = values["Interaction Availability"] || "Device state unavailable";
      const ready = availability.includes("READY");
      const voiceState = values["Voice State"] || "";
      const presentation = friendlyVoiceState(availability, voiceState);
      const livePill = hero.querySelector("[data-live-pill]");
      livePill.classList.toggle("busy", presentation.kind === "busy");
      livePill.classList.toggle("error", presentation.kind === "error");
      livePill.textContent = presentation.kind === "ready" ? "Online · Ready" : presentation.kind === "error" ? "Attention needed" : "Online · Busy";
      const orb = hero.querySelector("[data-voice-orb]");
      orb.classList.toggle("busy", presentation.kind === "busy");
      orb.classList.toggle("error", presentation.kind === "error");
      hero.querySelector("[data-voice-kicker]").textContent = presentation.kicker;
      hero.querySelector("[data-voice-title]").textContent = presentation.title;
      hero.querySelector("[data-voice-copy]").textContent = presentation.copy;
      hero.querySelector("[data-last-heard]").textContent = values["Heard (Exact STT)"] || "Nothing heard yet";
      hero.querySelector("[data-last-reply]").textContent = values["Assistant Reply (Exact)"] || values["Last Error"] || "No reply yet";
      hero.querySelector("[data-stat-pipeline]").textContent = voiceState.replaceAll("_", " ") || "Waiting";
      hero.querySelector("[data-stat-time]").textContent = values["Total Busy Time"] || "—";
      hero.querySelector("[data-stat-wifi]").textContent = values["Wi-Fi Signal"] || "—";
      const freeHeap = values["Free Heap"] || "";
      const freePsram = values["Free PSRAM"] || "";
      hero.querySelector("[data-stat-memory]").textContent = freePsram || freeHeap || "—";
      const volume = Math.round(parseFloat(values["Speaker Volume"]));
      const volumeRange = hero.querySelector("[data-volume-range]");
      if (Number.isFinite(volume)) {
        hero.querySelector("[data-volume-value]").textContent = volume;
        if (root.activeElement !== volumeRange) volumeRange.value = volume;
      }
      const preRoll = Math.round(parseFloat(values["One-Breath Pre-roll"]));
      const preRollRange = hero.querySelector("[data-preroll-range]");
      if (Number.isFinite(preRoll)) {
        hero.querySelector("[data-preroll-value]").textContent = `${preRoll} ms`;
        if (root.activeElement !== preRollRange) preRollRange.value = preRoll;
      }
      hero.querySelectorAll("[data-device-switch]").forEach((control) => {
        control.setAttribute("aria-pressed", values[control.dataset.deviceSwitch] === "Enabled" ? "true" : "false");
      });
      tabs.querySelector("[data-sidebar-heard]").textContent = values["Heard (Exact STT)"] || "No transcript yet";
      tabs.querySelector("[data-sidebar-reply]").textContent = values["Assistant Reply (Exact)"] || "No reply yet";
      tabs.querySelector("[data-sidebar-timing]").textContent = values["Last Pipeline Timing"] || "Waiting for timing";
      const sidebarReady = tabs.querySelector("[data-sidebar-ready]");
      const hasError = availability.includes("ERROR") || availability.includes("UNAVAILABLE");
      sidebarReady.classList.toggle("busy", !ready && !hasError);
      sidebarReady.classList.toggle("error", hasError);
      tabs.querySelector("[data-sidebar-ready-text]").textContent = ready ? "Ready" : hasError ? "Unavailable" : "Busy";
    };
    updateHero();
    setInterval(updateHero, 1000);

    const postDeviceAction = async (path, button, successMessage) => {
      if (button) button.disabled = true;
      try {
        const response = await fetch(path, {method:"POST"});
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        showToast(successMessage);
      } catch (error) {
        console.warn("Device control failed", error);
        showToast("Could not reach the device");
      } finally {
        if (button) setTimeout(() => { button.disabled = false; }, 350);
      }
    };
    const setNumber = (name, value, button, message) => postDeviceAction(`/number/${encodeURIComponent(name)}/set?value=${encodeURIComponent(value)}`, button, message);
    hero.addEventListener("input", (event) => {
      if (event.target.matches("[data-volume-range]")) hero.querySelector("[data-volume-value]").textContent = event.target.value;
      if (event.target.matches("[data-preroll-range]")) hero.querySelector("[data-preroll-value]").textContent = `${event.target.value} ms`;
    });
    hero.addEventListener("change", (event) => {
      if (event.target.matches("[data-volume-range]")) setNumber("Speaker Volume", event.target.value, event.target, `Volume set to ${event.target.value}%`);
      if (event.target.matches("[data-preroll-range]")) setNumber("One-Breath Pre-roll", event.target.value, event.target, `Buffer set to ${event.target.value} ms`);
    });
    hero.addEventListener("click", (event) => {
      const step = event.target.closest("[data-volume-step]");
      if (step) {
        const range = hero.querySelector("[data-volume-range]");
        const next = Math.max(Number(range.min), Math.min(Number(range.max), Number(range.value) + Number(step.dataset.volumeStep)));
        range.value = next;
        hero.querySelector("[data-volume-value]").textContent = next;
        setNumber("Speaker Volume", next, step, `Volume set to ${next}%`);
        return;
      }
      const toggle = event.target.closest("[data-device-switch]");
      if (toggle) {
        const name = toggle.dataset.deviceSwitch;
        const enabled = toggle.getAttribute("aria-pressed") === "true";
        postDeviceAction(`/switch/${encodeURIComponent(name)}/${enabled ? "turn_off" : "turn_on"}`, toggle, `${name} ${enabled ? "off" : "on"}`);
        return;
      }
      const button = event.target.closest("[data-device-button]");
      if (!button) return;
      if (button.dataset.confirm && !confirm(button.dataset.confirm)) return;
      postDeviceAction(`/button/${encodeURIComponent(button.dataset.deviceButton)}/press`, button, `${button.textContent.trim()} requested`);
    });

    let sessions = readSessions();
    const list = page.querySelector(".codex-session-list");
    const count = tabs.querySelector("[data-session-count]");
    const reportCount = tabs.querySelector("[data-report-count]");
    const diagnosticsUrlInput = page.querySelector("[data-diagnostics-url]");
    const diagnosticsStatus = page.querySelector("[data-diagnostics-status]");
    let expandedId = "";
    let researchStatus = null;
    let researchReports = [];
    const reportDrafts = new Map();
    let diagnosticsBaseUrl = localStorage.getItem(DIAGNOSTICS_URL_KEY) || "";
    diagnosticsUrlInput.value = diagnosticsBaseUrl;

    const acousticPanel = (session, row) => {
      const diagnostic = session.acoustic;
      if (!diagnostic) {
        return `<div class="codex-acoustic-box"><div class="codex-recognition-title">Deep acoustic diagnostics</div><div class="codex-protocol-note">No recognizer capture exists for this interaction. This is expected when the pipeline stopped before Speech-to-Phrase received audio; the device outcome, error, and timing evidence are still retained above.</div></div>`;
      }
      const decoder = diagnostic.decoder || {};
      const audio = diagnostic.audio || {};
      const metrics = audio.metrics || {};
      const candidates = decoder.candidates || [];
      const wordEvidence = decoder.word_evidence || [];
      const issueText = (audio.issues || []).length ? audio.issues.join(", ") : "None detected";
      const candidateRows = candidates.map((candidate) => `<tr><td>${Number(candidate.rank || 0)}</td><td>${escapeHtml(candidate.text || "")}</td><td>${escapeHtml(candidate.acoustic_cost ?? "NA")}</td><td>${escapeHtml(candidate.language_cost ?? "NA")}</td><td>${escapeHtml(candidate.total_cost ?? "NA")}</td></tr>`).join("");
      const wordRows = wordEvidence.map((word) => `<tr><td>${escapeHtml(word.word || "")}</td><td>${Number(word.start_ms || 0)}ms</td><td>${Number(word.duration_ms || 0)}ms</td><td>${escapeHtml(word.confidence ?? "NA")}</td></tr>`).join("");
      const audioUrl = diagnostic.audio_available && session.diagnostics_base_url
        ? `${session.diagnostics_base_url}/audio/${encodeURIComponent(diagnostic.id)}.wav`
        : "";
      return `<div class="codex-acoustic-box"><div class="codex-recognition-title">Deep acoustic diagnostics</div>
        ${row("Record", diagnostic.id)}${row("Raw best", decoder.raw_best_text || "No candidate")}${row("Fuzzy result", decoder.fuzzy_text || "No fuzzy match")}${row("Final", decoder.final_text || "No transcript")}${row("Fuzzy cost", decoder.fuzzy_cost ?? "NA")}${row("Score margin", decoder.score_margin ?? "NA")}${row("Decoder", decoder.status)}
        ${row("Signal", `Peak ${metrics.peak_dbfs ?? "NA"} dBFS | RMS ${metrics.rms_dbfs ?? "NA"} dBFS | estimated SNR ${metrics.estimated_snr_db ?? "NA"} dB | clipping ${metrics.clipping_percent ?? 0}%`)}
        ${row("Boundaries", `Leading silence ${metrics.leading_silence_ms ?? 0}ms | trailing silence ${metrics.trailing_silence_ms ?? 0}ms | active tail ${metrics.tail_active ? "YES" : "no"}`)}${row("Warnings", issueText)}
        ${candidateRows ? `<table class="codex-candidates"><thead><tr><th>Rank</th><th>Candidate</th><th>Acoustic cost</th><th>Grammar cost</th><th>Total</th></tr></thead><tbody>${candidateRows}</tbody></table>` : ""}
        ${wordRows ? `<table class="codex-candidates"><thead><tr><th>Word</th><th>Start</th><th>Duration</th><th>Lattice confidence</th></tr></thead><tbody>${wordRows}</tbody></table>` : ""}
        ${audioUrl ? `<audio class="codex-acoustic-audio" controls preload="none" src="${escapeHtml(audioUrl)}"></audio>` : ""}
        <div class="codex-protocol-note">Lower decoder cost is better. The score margin is candidate 2 total cost minus candidate 1; a small positive margin means the two phrases were acoustically close. Fuzzy cost measures how much correction was needed after decoding.</div>
      </div>`;
    };

    const formatBytes = (value) => {
      const bytes = Number(value || 0);
      if (bytes < 1024) return `${bytes} B`;
      if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KiB`;
      return `${(bytes / 1048576).toFixed(1)} MiB`;
    };

    const renderResearch = () => {
      const stats = page.querySelector("[data-research-stats]");
      const state = page.querySelector("[data-research-state]");
      const reportsList = page.querySelector("[data-report-list]");
      const capacityLabel = page.querySelector("[data-capacity-label]");
      const capacityFill = page.querySelector("[data-capacity-fill]");
      reportsList.querySelectorAll("[data-report-id]").forEach((card) => {
        const draft = card.querySelector("[data-report-summary]")?.value;
        if (draft !== undefined) reportDrafts.set(card.dataset.reportId, draft);
      });
      reportCount.hidden = !researchReports.length;
      reportCount.textContent = researchReports.length ? `${researchReports.length} reports` : "";
      tabs.querySelector("[data-sidebar-report-meta]").textContent = researchReports.length ? `${researchReports.length} report${researchReports.length === 1 ? "" : "s"}` : "Evidence";
      if (!researchStatus) {
        stats.innerHTML = '<div class="codex-research-stat"><strong>--</strong><span>Raw sessions</span></div><div class="codex-research-stat"><strong>--</strong><span>Reports</span></div><div class="codex-research-stat"><strong>--</strong><span>Analyzed</span></div><div class="codex-research-stat"><strong>--</strong><span>Pending</span></div>';
        state.textContent = "Waiting for diagnostics";
        capacityLabel.textContent = "0%";
        capacityFill.style.width = "0%";
        return;
      }
      const pressure = Math.max(Number(researchStatus.record_percent || 0), Number(researchStatus.storage_percent || 0));
      const boundedPressure = Math.min(100, pressure);
      state.textContent = researchStatus.pending_reports ? `${researchStatus.pending_reports} report${researchStatus.pending_reports === 1 ? "" : "s"} ready for analysis` : "Archive healthy";
      stats.innerHTML = `
        <div class="codex-research-stat"><strong>${Number(researchStatus.raw_records || 0)}</strong><span>Raw sessions</span><small>limit ${Number(researchStatus.record_limit || 0)}</small></div>
        <div class="codex-research-stat"><strong>${Number(researchStatus.reports || 0)}</strong><span>Reports</span><small>preserved</small></div>
        <div class="codex-research-stat success"><strong>${Number(researchStatus.analyzed_reports || 0)}</strong><span>Analyzed</span><small>with conclusions</small></div>
        <div class="codex-research-stat warning"><strong>${Number(researchStatus.pending_reports || 0)}</strong><span>Pending</span><small>needs review</small></div>`;
      capacityLabel.textContent = `${pressure.toFixed(1)}% | ${formatBytes(researchStatus.raw_bytes)} of ${formatBytes(researchStatus.storage_limit_bytes)}`;
      capacityFill.style.width = `${boundedPressure}%`;
      capacityFill.classList.toggle("warning", pressure >= 80);
      reportsList.innerHTML = researchReports.length ? researchReports.map((report) => {
        const analysis = report.analysis || {};
        const analyzed = analysis.status === "analyzed";
        const recommendations = (report.recommendations || []).slice(0, 3);
        return `<article class="codex-report-card ${analyzed ? "analyzed" : "pending"}" data-report-id="${escapeHtml(report.report_id)}">
          <div class="codex-report-summary"><div><strong>${escapeHtml(report.report_id)}</strong><span>${escapeHtml(new Date(report.created_at).toLocaleString())}</span></div><span class="codex-report-badge">${analyzed ? "Analyzed" : "Pending analysis"}</span></div>
          <div class="codex-report-metrics"><span>${Number(report.session_count || 0)} sessions</span><span>${Number(report.reviewed_count || 0)} reviewed</span><span>${Number(report.review_coverage_percent || 0)}% coverage</span></div>
          <ul>${recommendations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
          <div class="codex-report-analysis"><textarea data-report-summary placeholder="Add the conclusions after Codex analyzes this report">${escapeHtml(reportDrafts.has(report.report_id) ? reportDrafts.get(report.report_id) : (analysis.summary || ""))}</textarea><div class="codex-report-buttons"><button class="codex-session-action" type="button" data-report-download>Download report</button><button class="codex-session-action" type="button" data-report-analyzed>${analyzed ? "Update analysis" : "Mark analyzed"}</button></div></div>
        </article>`;
      }).join("") : '<div class="codex-report-empty">No completed research reports yet. A report is generated before raw data rolls over by record count or storage size.</div>';
    };

    const reviewSyncKey = (session) => JSON.stringify([session.review || "", session.expected_speech || "", session.review_note || "", session.acoustic?.id || ""]);
    const syncReview = async (session) => {
      if (!diagnosticsBaseUrl || !session.acoustic?.id) return;
      const key = reviewSyncKey(session);
      if (session.review_sync_key === key) return;
      try {
        const {acoustic: _acoustic, diagnostics_base_url: _baseUrl, review_sync_key: _syncKey, ...deviceSession} = session;
        const response = await fetch(`${diagnosticsBaseUrl}/api/sessions/${encodeURIComponent(session.acoustic.id)}/review`, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            review: session.review || "",
            expected_speech: session.expected_speech || "",
            review_note: session.review_note || "",
            device_session_id: session.id,
            device_session: deviceSession,
          }),
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        session.review_sync_key = key;
        saveSessions(sessions);
      } catch (error) {
        console.warn("Unable to synchronize voice review", error);
      }
    };

    const render = () => {
      renderResearch();
      count.textContent = `(${sessions.length})`;
      const inboxStats = page.querySelector("[data-inbox-stats]");
      const isErrorOutcome = (session) => Boolean(session.error) || (!session.ok && /ERROR|FAILED|FAILURE|TIMEOUT|NO TRANSCRIPT|NO AUDIO/i.test(session.outcome || ""));
      const successfulCount = sessions.filter((session) => !session.error && session.ok).length;
      const errorCount = sessions.filter(isErrorOutcome).length;
      const unreviewedCount = sessions.filter((session) => !session.review).length;
      inboxStats.innerHTML = `<div class="voice-lab-inbox-stat"><strong>${sessions.length}</strong><span>Total evidence</span></div><div class="voice-lab-inbox-stat needs-review"><strong>${unreviewedCount}</strong><span>Needs review</span></div><div class="voice-lab-inbox-stat success"><strong>${successfulCount}</strong><span>Successful</span></div><div class="voice-lab-inbox-stat error"><strong>${errorCount}</strong><span>Errors</span></div>`;
      if (!sessions.length) {
        list.innerHTML = '<div class="codex-session-empty">No packaged sessions yet. The next completed Hey Burden interaction will appear here automatically.</div>';
        return;
      }
      if (!expandedId || !sessions.some((session) => session.id === expandedId)) expandedId = sessions[0].id;
      const s = sessions.find((session) => session.id === expandedId) || sessions[0];
      const cardClass = isErrorOutcome(s) ? "error" : s.ok ? "ok" : "";
      const row = (label, value) => value ? `<div class="codex-session-row"><div class="codex-session-label">${label}</div><div class="codex-session-value">${escapeHtml(value)}</div></div>` : "";
      const timing = (label, value) => `<span class="codex-timing">${label} ${Number(value || 0)}ms</span>`;
      const reviews = [["correct","Correct"],["wrong_stt","Wrong recognition"],["wrong_action","Wrong action"],["missed_audio","Missed audio"]];
      const evidence = recognitionEvidence(s);
      const selectedReview = reviews.find(([value]) => value === s.review)?.[1] || "";
      const outcomeFlag = (session) => isErrorOutcome(session)
        ? '<span class="evidence-result-flag error">Error</span>'
        : session.ok
          ? '<span class="evidence-result-flag success">Successful</span>'
          : '<span class="evidence-result-flag captured">Captured</span>';
      const queue = sessions.map((session) => {
        const stateClass = isErrorOutcome(session) ? "error" : session.ok ? "ok" : "";
        const reviewDot = session.review ? "" : '<span class="evidence-review-dot" title="Needs review" aria-label="Needs review"></span>';
        return `<button type="button" class="codex-session-choice ${stateClass} ${session.id === s.id ? "active" : ""}" data-select-session="${escapeHtml(session.id)}"><div class="codex-session-choice-top"><span class="codex-session-choice-heard">${escapeHtml(session.heard || "No transcript")}</span><span class="codex-session-choice-badges">${reviewDot}${outcomeFlag(session)}</span></div><span class="codex-session-choice-meta">${escapeHtml(new Date(session.received_at).toLocaleString())} · ${Number(session.total_ms || 0)}ms</span><span class="codex-session-choice-meta">${escapeHtml(session.id)}</span></button>`;
      }).join("");
      list.innerHTML = `<div class="codex-research-workspace"><aside class="codex-session-queue">${queue}</aside><article class="codex-selected-session ${cardClass}" data-session-id="${escapeHtml(s.id)}">
        <section class="codex-selected-hero"><div class="voice-selected-status">${outcomeFlag(s)}${s.review ? `<span class="voice-review-state reviewed">Reviewed · ${escapeHtml(selectedReview)}</span>` : '<span class="voice-review-state"><span class="evidence-review-dot" aria-hidden="true"></span>Needs review</span>'}</div><h3>${escapeHtml(s.heard || "No transcript")}</h3><p>${escapeHtml(s.reply || s.error || "No assistant response was recorded.")} · ${Number(s.total_ms || 0)}ms total</p></section>
        <div class="codex-detail-grid">
          <section class="codex-detail-panel"><div class="codex-detail-title"><span>Conversation result</span><span class="codex-session-outcome">${escapeHtml(s.outcome)}</span></div>${row("Wake", s.wake)}${row("Heard", s.heard || "No transcript")}${row("Reply", s.reply)}${row("Matched", s.matched)}${row("Result", s.result)}${row("Error", s.error)}</section>
          <section class="codex-recognition-box"><div class="codex-recognition-title">Recognition decision</div>${row("Normalized", evidence.normalized)}${row("Decision", evidence.decision)}${row("Evidence", evidence.evidence)}${row("Routing", evidence.route)}<div class="codex-protocol-note">This is the final Wyoming transcript and Home Assistant routing decision. Decoder alternatives and acoustic evidence are preserved below.</div></section>
          <section class="codex-detail-panel full"><div class="codex-detail-title">Acoustic decoder evidence</div>${acousticPanel(s, row)}</section>
          <section class="codex-detail-panel full"><div class="codex-detail-title">Request timeline</div><div class="codex-timing-strip">${timing("Wake to pipeline",s.wake_pipeline_ms)}${timing("Replay",s.replay_ms)}${timing("Wake to speech",s.wake_speech_ms)}${timing("Capture",s.capture_ms)}${timing("STT",s.stt_ms)}${timing("Action",s.action_ms)}${timing("Total",s.total_ms)}</div><div class="codex-session-row"><div class="codex-session-label">Capture</div><div class="codex-session-value">${s.one_breath ? "One-breath candidate" : "Pause or undetected"} | ${Number(s.replay_bytes || 0)} replay bytes | ${Number(s.pre_roll_ms || 0)}ms pre-roll | ${Number(s.rssi_dbm || 0)}dBm</div></div></section>
          <section class="codex-detail-panel full"><div class="codex-detail-title"><span>Human review</span><span class="codex-protocol-note">Synchronized to the next research report</span></div><div class="codex-review">${reviews.map(([value,label]) => `<button type="button" data-review="${value}" class="${s.review === value ? "selected" : ""}">${label}</button>`).join("")}</div><div class="codex-review-fields"><label>What you actually said<input data-field="expected_speech" value="${escapeHtml(s.expected_speech || "")}" placeholder="Example: turn off the lights"></label><label>Review note / expected result<input data-field="review_note" value="${escapeHtml(s.review_note || "")}" placeholder="Example: should have turned both lights off"></label></div></section>
        </div>
      </article></div>`;
    };

    const renderPage = () => {
      const sessionsPage = window.location.hash === PAGE_SESSIONS;
      overview.hidden = sessionsPage;
      hero.hidden = sessionsPage;
      page.hidden = !sessionsPage;
      tabs.querySelectorAll("[data-view]").forEach((item) => item.classList.toggle("active", (item.dataset.view === "sessions") === sessionsPage));
      tabs.querySelector("[data-sidebar-workspace]").textContent = sessionsPage ? "Session evidence" : "Live operations";
      document.title = sessionsPage ? "Voice Research Sessions" : "ESP32 Voice Assistant";
    };
    window.addEventListener("hashchange", renderPage);
    if (!window.location.hash) history.replaceState(null, "", PAGE_OVERVIEW);

    page.addEventListener("click", (event) => {
      const sessionChoice = event.target.closest("[data-select-session]");
      if (sessionChoice) {
        expandedId = sessionChoice.dataset.selectSession;
        render();
        return;
      }
      const review = event.target.closest("[data-review]");
      if (review) {
        const card = review.closest("[data-session-id]");
        const session = sessions.find((item) => item.id === card?.dataset.sessionId);
        if (session) { session.review = review.dataset.review; session.review_sync_key = ""; saveSessions(sessions); syncReview(session); render(); }
        return;
      }
      const reportButton = event.target.closest("[data-report-analyzed]");
      if (reportButton) {
        const card = reportButton.closest("[data-report-id]");
        const summary = card?.querySelector("[data-report-summary]")?.value.trim() || "";
        const reportId = card?.dataset.reportId;
        if (reportId && diagnosticsBaseUrl) {
          reportButton.disabled = true;
          fetch(`${diagnosticsBaseUrl}/api/reports/${encodeURIComponent(reportId)}/analysis`, {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({status: "analyzed", summary}),
          }).then((response) => {
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return refreshDiagnostics(true);
          }).catch((error) => {
            reportButton.disabled = false;
            console.warn("Unable to save report analysis", error);
          });
        }
        return;
      }
      const reportDownload = event.target.closest("[data-report-download]");
      if (reportDownload) {
        const reportId = reportDownload.closest("[data-report-id]")?.dataset.reportId;
        if (reportId && diagnosticsBaseUrl) {
          fetch(`${diagnosticsBaseUrl}/api/reports/${encodeURIComponent(reportId)}`, {cache:"no-store"})
            .then((response) => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
            .then((report) => download(`${reportId}.json`, "application/json", JSON.stringify(report, null, 2)))
            .catch((error) => console.warn("Unable to download research report", error));
        }
        return;
      }
      if (event.target.closest("[data-diagnostics-connect]")) {
        diagnosticsBaseUrl = diagnosticsUrlInput.value.trim().replace(/\/+$/, "");
        if (diagnosticsBaseUrl) localStorage.setItem(DIAGNOSTICS_URL_KEY, diagnosticsBaseUrl);
        else localStorage.removeItem(DIAGNOSTICS_URL_KEY);
        refreshDiagnostics(true);
        return;
      }
      const exportButton = event.target.closest("[data-export]");
      if (exportButton) {
        const stamp = new Date().toISOString().replaceAll(":", "-");
        if (exportButton.dataset.export === "json") download(`voice-sessions-${stamp}.json`, "application/json", JSON.stringify(sessions, null, 2));
        else download(`voice-sessions-${stamp}.csv`, "text/csv", toCsv(sessions));
        return;
      }
      if (event.target.closest("[data-clear]") && confirm("Clear the locally packaged session history in this browser? Home Assistant Recorder data is not affected.")) {
        sessions = []; saveSessions(sessions); render();
      }
    });
    page.addEventListener("change", (event) => {
      const field = event.target.closest("[data-field]");
      if (!field) return;
      const selected = field.closest("[data-session-id]");
      const session = sessions.find((item) => item.id === selected?.dataset.sessionId);
      if (session) { session[field.dataset.field] = field.value.trim(); session.review_sync_key = ""; saveSessions(sessions); syncReview(session); }
    });

    const ingestRows = () => {
      rows.querySelectorAll(".trow:not([data-session-scanned])").forEach((row) => {
        row.dataset.sessionScanned = "true";
        const message = row.children[3]?.textContent || row.textContent || "";
        const marker = "SESSION_JSON ";
        const start = message.indexOf(marker);
        if (start < 0) return;
        try {
          const record = JSON.parse(message.slice(start + marker.length));
          if (!record.id) return;
          const previous = sessions.find((item) => item.id === record.id);
          const now = Date.now();
          const diagnosticText = normalizeTranscript(record.heard);
          const imported = previous ? null : sessions.find((item) => {
            if (!item.synthetic || !item.acoustic) return false;
            const completed = new Date(item.acoustic.completed_at || item.acoustic.started_at).getTime();
            return Number.isFinite(completed)
              && now - completed >= -3000
              && now - completed <= 120000
              && normalizeTranscript(item.acoustic.decoder?.final_text) === diagnosticText;
          });
          const packaged = previous || imported;
          record.received_at = packaged?.received_at || new Date().toISOString();
          record.review = packaged?.review || "";
          record.expected_speech = packaged?.expected_speech || "";
          record.review_note = packaged?.review_note || "";
          record.acoustic = packaged?.acoustic;
          record.diagnostics_base_url = packaged?.diagnostics_base_url;
          sessions = [record, ...sessions.filter((item) => item.id !== record.id && item !== imported)].slice(0, MAX_SESSIONS);
          saveSessions(sessions);
          if (record.acoustic) syncReview(record);
          render();
        } catch (_error) {
          // Leave malformed/truncated records visible in Debug Log for diagnosis.
        }
      });
    };

    const sessionFromDiagnostic = (diagnostic) => {
      const serverReview = diagnostic.review || {};
      const deviceSession = serverReview.device_session && typeof serverReview.device_session === "object"
        ? serverReview.device_session
        : {};
      const decoder = diagnostic.decoder || {};
      const decoderStatus = String(decoder.status || "UNKNOWN");
      const recognized = decoderStatus === "OK";
      const sessionId = deviceSession.id || serverReview.device_session_id || `diagnostic-${diagnostic.id}`;
      return {
        ...deviceSession,
        id: sessionId,
        received_at: deviceSession.received_at || diagnostic.completed_at || diagnostic.started_at || new Date().toISOString(),
        wake: deviceSession.wake || "Wake captured upstream",
        heard: deviceSession.heard || decoder.final_text || "",
        reply: deviceSession.reply || "",
        matched: deviceSession.matched || "",
        result: deviceSession.result || "",
        error: deviceSession.error || (recognized ? "" : `Speech recognition: ${decoderStatus}`),
        outcome: deviceSession.outcome || (recognized ? "TRANSCRIBED - ROUTING RECORD NOT CAPTURED" : `STT FAILED - ${decoderStatus}`),
        ok: Boolean(deviceSession.ok),
        review: serverReview.review || "",
        expected_speech: serverReview.expected_speech || "",
        review_note: serverReview.review_note || "",
        acoustic: diagnostic,
        diagnostics_base_url: diagnosticsBaseUrl,
        synthetic: String(sessionId).startsWith("diagnostic-"),
      };
    };

    const correlateDiagnostics = (records) => {
      const claimed = new Set(sessions.map((session) => session.acoustic?.id).filter(Boolean));
      let changed = false;
      for (const diagnostic of records) {
        if (!diagnostic?.id) continue;
        const existing = sessions.find((session) => session.acoustic?.id === diagnostic.id);
        if (existing) {
          existing.acoustic = diagnostic;
          existing.diagnostics_base_url = diagnosticsBaseUrl;
          const serverReview = diagnostic.review || {};
          if (!existing.review && serverReview.review) { existing.review = serverReview.review; changed = true; }
          if (!existing.expected_speech && serverReview.expected_speech) { existing.expected_speech = serverReview.expected_speech; changed = true; }
          if (!existing.review_note && serverReview.review_note) { existing.review_note = serverReview.review_note; changed = true; }
          continue;
        }
        if (claimed.has(diagnostic.id)) continue;
        const diagnosticText = normalizeTranscript(diagnostic.decoder?.final_text);
        const diagnosticTime = new Date(diagnostic.completed_at || diagnostic.started_at).getTime();
        let best = null;
        let bestDistance = Infinity;
        const serverDeviceId = diagnostic.review?.device_session_id;
        if (serverDeviceId) best = sessions.find((session) => session.id === serverDeviceId && !session.acoustic) || null;
        for (const session of sessions) {
          if (best) break;
          if (session.acoustic) continue;
          const sessionTime = new Date(session.received_at).getTime();
          const distance = sessionTime - diagnosticTime;
          if (!Number.isFinite(distance) || distance < -3000 || distance > 120000) continue;
          const sessionText = normalizeTranscript(session.heard);
          if (sessionText !== diagnosticText) continue;
          if (distance < bestDistance) { best = session; bestDistance = distance; }
        }
        if (best) {
          best.acoustic = diagnostic;
          best.diagnostics_base_url = diagnosticsBaseUrl;
          const serverReview = diagnostic.review || {};
          if (!best.review && serverReview.review) best.review = serverReview.review;
          if (!best.expected_speech && serverReview.expected_speech) best.expected_speech = serverReview.expected_speech;
          if (!best.review_note && serverReview.review_note) best.review_note = serverReview.review_note;
          claimed.add(diagnostic.id);
          changed = true;
        } else {
          const imported = sessionFromDiagnostic(diagnostic);
          sessions = [imported, ...sessions.filter((session) => session.id !== imported.id)];
          claimed.add(diagnostic.id);
          changed = true;
        }
      }
      if (changed) {
        const timestamp = (session) => {
          const value = new Date(session.received_at).getTime();
          return Number.isFinite(value) ? value : 0;
        };
        sessions = sessions.sort((left, right) => timestamp(right) - timestamp(left)).slice(0, MAX_SESSIONS);
        saveSessions(sessions);
        render();
      }
      return changed;
    };

    const refreshDiagnostics = async (manual = false) => {
      if (!diagnosticsBaseUrl) {
        diagnosticsStatus.textContent = "Not configured";
        return;
      }
      diagnosticsStatus.textContent = "Connecting...";
      try {
        const [sessionsResponse, reportsResponse] = await Promise.all([
          fetch(`${diagnosticsBaseUrl}/api/sessions?limit=${MAX_SESSIONS}`, {cache:"no-store"}),
          fetch(`${diagnosticsBaseUrl}/api/reports`, {cache:"no-store"}),
        ]);
        if (!sessionsResponse.ok) throw new Error(`HTTP ${sessionsResponse.status}`);
        if (!reportsResponse.ok) throw new Error(`Reports HTTP ${reportsResponse.status}`);
        const [payload, reportsPayload] = await Promise.all([sessionsResponse.json(), reportsResponse.json()]);
        const records = Array.isArray(payload.sessions) ? payload.sessions : [];
        researchStatus = payload.research || null;
        researchReports = Array.isArray(reportsPayload.reports) ? reportsPayload.reports : [];
        correlateDiagnostics(records);
        sessions.filter((session) => session.acoustic && !session.synthetic).forEach(syncReview);
        renderResearch();
        diagnosticsStatus.textContent = `Connected | ${records.length} raw record${records.length === 1 ? "" : "s"} | ${researchReports.length} report${researchReports.length === 1 ? "" : "s"}`;
      } catch (error) {
        diagnosticsStatus.textContent = `Unavailable | ${error.message}`;
        if (manual) console.warn("Voice diagnostics connection failed", error);
      }
    };

    new MutationObserver(ingestRows).observe(rows, {childList:true, subtree:true});
    ingestRows();
    render();
    renderPage();
    // Reveal only after the custom shell is complete. The tiny blocking CSS
    // resource arrives before this much larger JavaScript bundle, preventing
    // the stock ESPHome shell from painting during download or enhancement.
    document.querySelector('link[href="/0.css"]')?.remove();
    refreshDiagnostics();
    setInterval(refreshDiagnostics, 4000);
  };

  wireSessionHistory();
  setInterval(wireSessionHistory, 500);
});
