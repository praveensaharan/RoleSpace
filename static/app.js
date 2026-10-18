"use strict";
// RoleSpace front end: one page, hash routes (#/assistant), persona in ?as=, no framework.
// Server data always goes through esc() before it reaches innerHTML. Buttons carry
// data-action attributes handled in one place, so the page runs under a strict CSP.

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const first = (name) => String(name || "").split(" ")[0];
const cap = (s) => String(s || "").charAt(0).toUpperCase() + String(s || "").slice(1);

function money(v) {
  if (v == null || isNaN(v)) return "–";
  const n = Number(v), a = Math.abs(n);
  return "$" + n.toFixed(a > 0 && a < 0.01 ? 4 : 2);
}
const parseTime = (s) => s == null ? NaN : typeof s === "number" ? s * 1000
  : Date.parse(/Z$|[+-]\d\d:\d\d$/.test(s) ? s : s + "Z");
function when(s) {
  const t = parseTime(s); if (isNaN(t)) return "–";
  return new Date(t).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
function ago(s) {
  const t = parseTime(s); if (isNaN(t)) return "";
  const m = Math.round((Date.now() - t) / 60000);
  return m < 1 ? "just now" : m < 60 ? `${m} min ago` : m < 1440 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} d ago`;
}
const clock = (epochSec) => new Date(epochSec * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

// Icons: paths from Lucide (ISC licence), drawn at 16px with a 1.75 stroke.
const ICONS = {
  message: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  inbox: '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
  terminal: '<polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/>',
  chart: '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
  file: '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/>',
  network: '<rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/><path d="M12 12V8"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
  pr: '<circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><line x1="6" x2="6" y1="9" y2="21"/>',
  plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
  chevron: '<path d="m9 18 6-6-6-6"/>',
  updown: '<path d="m7 15 5 5 5-5"/><path d="m7 9 5-5 5 5"/>',
  lock: '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  key: '<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  ban: '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
  clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  power: '<path d="M12 2v10"/><path d="M18.4 6.6a9 9 0 1 1-12.77.04"/>',
  external: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  book: '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
  zap: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
  help: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
  branch: '<line x1="6" x2="6" y1="3" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/>',
  server: '<rect width="20" height="8" x="2" y="2" rx="2"/><rect width="20" height="8" x="2" y="14" rx="2"/><line x1="6" x2="6.01" y1="6" y2="6"/><line x1="6" x2="6.01" y1="18" y2="18"/>',
  play: '<polygon points="6 3 20 12 6 21 6 3"/>',
  sliders: '<line x1="4" x2="4" y1="21" y2="14"/><line x1="4" x2="4" y1="10" y2="3"/><line x1="12" x2="12" y1="21" y2="12"/><line x1="12" x2="12" y1="8" y2="3"/><line x1="20" x2="20" y1="21" y2="16"/><line x1="20" x2="20" y1="12" y2="3"/><line x1="2" x2="6" y1="14" y2="14"/><line x1="10" x2="14" y1="8" y2="8"/><line x1="18" x2="22" y1="16" y2="16"/>',
};
const icon = (name, cls = "") => `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ""}</svg>`;
// The mark: four rising bars, the role ladder (Ask, Suggest, Build, Govern).
const logo = (size = 16) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" aria-hidden="true">
  <rect x="3" y="15" width="3.2" height="6" rx="1" fill="#fff"/><rect x="8.3" y="11" width="3.2" height="10" rx="1" fill="#fff"/>
  <rect x="13.6" y="7" width="3.2" height="14" rx="1" fill="#fff"/><rect x="18.9" y="3" width="3.2" height="18" rx="1" fill="#fff"/></svg>`;

const LEVEL_TEXT = {
  ask: "Questions about the code, answered with checked citations. No changes.",
  suggest: "Small edits inside an allow-list, delivered as a pull request a human merges.",
  build: "A private Coder workspace with Gemini CLI on your own key.",
  govern: "Levels, budgets, spend, approvals and the audit trail.",
};
const TOOL_LABELS = { list_files: "List files", search_code: "Search code", read_file: "Read files",
  draft_request: "Send a request to the owning team", propose_edit: "Propose edits, as a pull request" };
const PROMPTS = {
  maya: ["How is a candidate's score calculated?", "Please lower the passing score to 40.",
         "Where is interview data stored?", "What happens when a candidate clicks Begin interview?"],
  leo: ["Make the Begin interview button our new brand colour #FF6B35 in public/css/app.css.",
        "Also change lib/score.mjs so the overall score is out of 10 instead of 100.",
        "Which CSS file styles the interview page?", "Summarise the candidate transcript export in docs/transcripts."],
  sam: ["What does server.mjs do, in five bullet points?", "How do I run this project locally?",
        "Which environment variables must be set?", "Where are the scoring dimensions defined?"],
  ava: ["Which files decide a candidate's recommendation?", "Which model does the app use for scoring?"],
};
const SUGGEST_EXTRA = ["Change the page title in public/index.html to \"FirstRound | Screening interviews\"."];
const PROJECT_PROMPTS = {
  rolespace: ["How does RoleSpace stop a person who is over budget?", "Where is the path allow-list for Suggest edits checked?",
              "How does the audit log detect a deleted event?", "Which models can each level use, and where is that decided?"],
  screener: ["What does this app do, in five bullet points?", "How is a candidate's score calculated?",
             "How do I run this project locally?", "Which environment variables must be set?"],
};

const S = { info: null, me: null, route: "assistant", chats: {}, busy: {}, renderId: 0, status: null, timers: {}, reqOpen: 0 };
const me = () => S.info.people.find((p) => p.id === S.me);
const isGov = (p) => p.level === "govern";

const ROUTES = {
  assistant: { label: "Assistant", icon: "message", group: "Work", render: renderAssistant },
  requests: { label: "Requests", icon: "inbox", group: "Work", render: renderRequests },
  changes: { label: "Changes", icon: "pr", group: "Work", show: (p) => p.tools.includes("propose_edit") || isGov(p), render: renderChanges },
  github: { label: "Issues & PRs", icon: "pr", group: "Work", render: renderGitHub },
  workspace: { label: "Workspace", icon: "terminal", group: "Work", show: (p) => p.level === "build", render: renderWorkspace },
  overview: { label: "Overview", icon: "chart", group: "Govern", show: isGov, render: renderOverview },
  usage: { label: "Usage", icon: "key", group: "Govern", show: isGov, render: renderUsage },
  people: { label: "People & access", icon: "users", group: "Govern", show: isGov, render: renderPeople },
  repos: { label: "Repo access", icon: "branch", group: "Govern", show: isGov, render: renderRepoAccess },
  policy: { label: "Policy", icon: "shield", group: "Govern", show: isGov, render: renderPolicy },
  audit: { label: "Audit log", icon: "file", group: "Govern", show: isGov, render: renderAudit },
  architecture: { label: "Architecture", icon: "network", group: "Govern", show: isGov, wide: true,
                  render: (el, id) => window.renderArch(el, id) },
};
const allowed = (route, p) => ROUTES[route] && (!ROUTES[route].show || ROUTES[route].show(p));

// ---- plumbing ----------------------------------------------------------------------------

// A random id per browser: the server keeps one conversation per browser and person.
const SESSION = localStorage.rsSession ||= (crypto.randomUUID?.() || String(Math.random()).slice(2) + Date.now());
const PASSCODE_NEEDED = "demo passcode required";

async function api(path, body, retried = false) {
  const headers = { "X-RS-Session": SESSION };
  if (localStorage.rsPasscode) headers["X-Demo-Passcode"] = localStorage.rsPasscode;
  if (body) headers["Content-Type"] = "application/json";
  let r;
  try {
    r = await fetch(path, body ? { method: "POST", headers, body: JSON.stringify(body) } : { headers });
  } catch {
    throw new Error("Can't reach RoleSpace. Check your connection and try again.");
  }
  const data = await r.json().catch(() => ({}));
  if (r.status === 401 && data.detail === PASSCODE_NEEDED && !retried) {
    delete localStorage.rsPasscode;
    if (await askPasscode()) return api(path, body, true);
    throw new Error("This action needs the demo admin passcode.");
  }
  if (!r.ok) {
    const d = data.detail;
    throw new Error((Array.isArray(d) ? d.map((x) => x.msg).join("; ") : d) || `Request failed (HTTP ${r.status}). Try again.`);
  }
  return data;
}

// The demo URL is public, so admin changes and pull requests ask for a passcode once per browser.
function askPasscode() {
  return new Promise((resolve) => modal({
    title: "Admin passcode", confirm: "Continue",
    sub: "This demo is public, so changes to budgets, access and the GitHub repo need the presenter's passcode. Everything else is open.",
    body: `<label class="field">Passcode<input class="input" name="code" type="password" autocomplete="current-password" required></label>`,
    onConfirm: (f) => { const code = String(f.get("code") || "").trim(); if (!code) return false; localStorage.rsPasscode = code; resolve(true); },
    onCancel: () => resolve(false),
  }));
}

function toast(msg, kind = "ok") {
  const t = document.createElement("div");
  t.className = "toast " + kind;
  t.setAttribute("role", kind === "bad" ? "alert" : "status");
  t.innerHTML = icon(kind === "bad" ? "alert" : "check") + `<div>${esc(msg)}</div>`;
  $("#toasts").append(t);
  setTimeout(() => t.remove(), kind === "bad" ? 7000 : 4000);
}

function modal({ title, sub = "", body, confirm, danger = false, onConfirm, onCancel, wide = false, cancelButton = true }) {
  const wrap = document.createElement("div");
  wrap.className = "backdrop";
  wrap.innerHTML = `<div class="modal${wide ? " wide" : ""}" role="dialog" aria-modal="true" aria-labelledby="modal-title">
    <div class="modal-head"><h3 id="modal-title">${esc(title)}</h3>${sub ? `<p>${esc(sub)}</p>` : ""}</div>
    <form class="modal-body" novalidate>${body}</form>
    <div class="modal-foot">${cancelButton ? `<button type="button" class="btn" data-close>Cancel</button>` : ""}
      <button type="button" class="btn ${danger ? "danger" : "primary"}" data-ok>${esc(confirm)}</button></div></div>`;
  const prevFocus = document.activeElement;
  let done = false;
  const close = () => { wrap.remove(); document.removeEventListener("keydown", onKey); prevFocus?.focus?.(); };
  const cancel = () => { close(); if (!done) onCancel?.(); };
  const onKey = (ev) => { if (ev.key === "Escape") cancel(); };
  const ok = $("[data-ok]", wrap);
  const submit = async (ev) => {
    ev?.preventDefault();
    if (ok.disabled) return;
    ok.disabled = true;
    try { if ((await onConfirm(new FormData($("form", wrap)))) !== false) { done = true; close(); } }
    catch (err) { toast(err.message, "bad"); }
    finally { ok.disabled = false; }
  };
  wrap.addEventListener("mousedown", (ev) => { if (ev.target === wrap) cancel(); });
  $("[data-close]", wrap)?.addEventListener("click", cancel);
  ok.addEventListener("click", submit);
  $("form", wrap).addEventListener("submit", submit);
  document.addEventListener("keydown", onKey);
  document.body.append(wrap);
  ($("input, select, textarea", wrap) || ok).focus();
}

function clearTimers() { Object.values(S.timers).forEach(clearInterval); S.timers = {}; }

// ---- boot, persona, routing --------------------------------------------------------------

async function boot() {
  S.info = await api("/api/people");
  const params = new URLSearchParams(location.search);
  const as = S.info.people.some((p) => p.id === params.get("as")) ? params.get("as") : S.info.people[0].id;
  setPersona(as, location.hash.replace(/^#\/?/, ""));
  window.addEventListener("hashchange", () => go(location.hash.replace(/^#\/?/, ""), false));
  refreshStatus(); setInterval(refreshStatus, 30000);
  setInterval(tickElapsed, 1000);
  if (!localStorage.rsWelcomed) welcome();
}

// First visit: ten seconds of orientation, then straight into a persona.
function welcome() {
  const w = document.createElement("div");
  w.className = "backdrop onboard";
  w.innerHTML = `<div class="modal wide" role="dialog" aria-modal="true" aria-labelledby="w-title">
    <div class="modal-head"><div class="mark">${logo(20)}</div><h3 id="w-title">Welcome to RoleSpace</h3>
      <p>Every role gets the right AI, and the company keeps control. One policy file gives each person a level, enforced in
        code, at the model gateway, in CI and in IAM. This demo is the ${esc(S.info.company)} team: pick someone to start as.</p></div>
    <div class="modal-body levels">${S.info.people.map((p) => `
      <button class="level-pick" data-action="welcome-start" data-id="${esc(p.id)}">
        <span class="avatar ${p.base_level}">${esc(p.name[0])}</span>
        <span class="who"><b>${esc(p.name)} <span class="muted">· ${esc(p.title)}</span></b><small>${esc(LEVEL_TEXT[p.base_level])}</small></span>
        <span class="lvl ${p.base_level}">${p.base_level}</span>${icon("chevron")}</button>`).join("")}</div>
    <div class="modal-foot"><span class="small muted" style="margin-right:auto">Switch any time from the menu at the bottom left.</span>
      <button class="btn primary" data-action="welcome-start" data-id="${esc(S.me)}">Start as ${esc(first(me().name))}</button></div></div>`;
  const done = () => { localStorage.rsWelcomed = "1"; w.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = (e) => { if (e.key === "Escape") done(); };
  w.addEventListener("mousedown", (e) => { if (e.target === w) done(); });
  document.addEventListener("keydown", onKey);
  document.body.append(w);
  $(".modal-foot [data-action=welcome-start]", w)?.focus();
}

function setPersona(id, route) {
  if (!S.chats[id]) { S.chats[id] = []; restoreChat(id); }  // a fresh page picks up where this browser left off
  S.me = id;
  const url = new URL(location.href);
  url.searchParams.set("as", id);
  history.replaceState(null, "", url);
  go(route || (isGov(me()) ? "overview" : "assistant"), true);
  refreshPeople();
}

async function refreshPeople() {  // levels change with approvals and expiry
  const who = S.me;
  try {
    const info = await api("/api/people");
    S.info = info;
    if (who === S.me) { renderNav(); if (S.route === "assistant") renderRail(); }
  } catch { /* keep what we have */ }
  refreshRequestCount();
}

function go(route, force) {
  const p = me();
  if (!allowed(route, p)) route = isGov(p) ? "overview" : "assistant";
  if (!force && route === S.route) return;
  S.route = route;
  if (location.hash !== "#/" + route) history.replaceState(null, "", "#/" + route);
  render();
}

function render() {
  clearTimers();
  const id = ++S.renderId, r = ROUTES[S.route];
  $("#app").innerHTML = `
    <aside class="sidebar">
      <div class="brand"><div class="mark">${logo()}</div><div><b>RoleSpace</b><small>${esc(S.info.company)} workspace</small></div></div>
      <nav class="nav" id="nav" aria-label="Main"></nav>
      <div class="grow"></div>
      <div class="account" id="account"></div>
    </aside>
    <div class="main">
      <header class="topbar">
        <div class="crumbs">${esc(S.info.company)} ${icon("chevron")} <b>${esc(r.label)}</b></div>
        <div class="spacer"></div>
        ${repoChip()}
        <span class="chip" title="Fingerprint of role.yaml as deployed">${icon("shield")} Policy <span class="mono">${esc(S.info.policy_version.slice(0, 7))}</span></span>
        <span class="chip" id="status-chip"><span class="dot"></span> Checking services…</span>
      </header>
      <main class="page ${r.wide ? "wide" : ""}" id="page"></main>
    </div>`;
  renderNav(); renderAccount(); paintStatus();
  r.render($("#page"), id);
  document.title = `${r.label} · RoleSpace`;
}

function renderNav() {
  const p = me(), nav = $("#nav");
  if (!nav) return;
  nav.innerHTML = ["Work", "Govern"].map((g) => {
    const items = Object.entries(ROUTES).filter(([k, r]) => r.group === g && allowed(k, p));
    const locked = (label, why) => `<span class="nav-item locked" title="${why}">${icon("lock")}<span>${label}</span></span>`;
    if (!items.length) return g === "Govern" ? `<div class="nav-label">Govern</div>
      ${locked("Govern level only", "Spend, people, policy and the audit log are for the Govern level")}` : "";
    return `<div class="nav-label">${g}</div>` + items.map(([k, r]) =>
      `<a class="nav-item ${S.route === k ? "on" : ""}" href="#/${k}" ${S.route === k ? 'aria-current="page"' : ""}>
        ${icon(r.icon)}<span>${r.label}</span>${k === "requests" && S.reqOpen ? `<span class="count">${S.reqOpen}</span>` : ""}</a>`).join("") +
      (g === "Work" && p.level !== "build" ? locked("Workspace · Build only", "A private dev workspace is for the Build level") : "");
  }).join("");
}

function renderAccount() {
  const p = me();
  $("#account").innerHTML = `
    <button class="account-btn" data-action="account-menu" aria-haspopup="menu" aria-expanded="false">
      <span class="avatar ${p.level}">${esc(p.name.split(" ").map((w) => w[0]).join(""))}</span>
      <span class="who"><b>${esc(p.name)}</b><small>${esc(p.title)}</small></span>${icon("updown")}</button>`;
}

function openAccountMenu(btn) {
  const existing = $(".menu");
  if (existing) { existing.remove(); btn.setAttribute("aria-expanded", "false"); return; }
  const m = document.createElement("div");
  m.className = "menu"; m.setAttribute("role", "menu");
  m.innerHTML = `<div class="menu-head">Switch persona (demo sign-in)</div>` + S.info.people.map((p) => `
    <button class="menu-item ${p.id === S.me ? "on" : ""}" role="menuitem" data-action="persona" data-id="${esc(p.id)}">
      <span class="avatar sm ${p.level}">${esc(p.name[0])}</span><span class="who"><b>${esc(p.name)}</b><small>${esc(p.title)}</small></span>
      <span class="lvl ${p.level}">${p.level}</span></button>`).join("") +
    `<div class="menu-foot">${icon("lock")} ${S.info.viewer
      ? `Signed in with Google as <b>${esc(S.info.viewer)}</b> through Identity-Aware Proxy. Personas stand in for directory groups in this demo.`
      : "In production, people sign in with Google through Identity-Aware Proxy, and their level comes from their directory group."}</div>`;
  $("#account").append(m);
  btn.setAttribute("aria-expanded", "true");
}

async function refreshStatus() {
  if (document.hidden && S.status) return;
  try { S.status = await api("/api/status"); } catch { S.status = { gateway: "unreachable" }; }
  paintStatus();
}
function paintStatus() {
  const chip = $("#status-chip"), s = S.status;
  if (!chip || !s) return;
  const ok = s.gateway === "up";
  chip.innerHTML = `<span class="dot ${ok ? "ok" : "bad"}"></span> ${ok ? "All systems normal" : "Gateway " + esc(s.gateway)}`;
  chip.title = `Model gateway: ${s.gateway} · Coder VM: ${s.coder_vm || "unknown"}`;
}

async function refreshRequestCount() {
  const who = S.me;
  try {
    const { requests } = await api("/api/requests?person=" + who);
    if (who !== S.me) return;
    S.reqOpen = requests.filter((r) => r.actions.some((a) => ["accept", "done", "approve"].includes(a))).length;
    renderNav();
  } catch { /* the badge is optional */ }
}

function tickElapsed() {
  $$("[data-since]").forEach((el) => { el.textContent = Math.max(0, Math.round((Date.now() - Number(el.dataset.since)) / 1000)) + " s"; });
}

// ---- Assistant -----------------------------------------------------------------------------

function renderAssistant(page) {
  const p = me();
  page.innerHTML = `<div class="assistant">
    <section class="panel thread" aria-label="Conversation">
      <div class="panel-head"><h2>Assistant <span class="sub">${cap(p.level)} level</span></h2>
        ${(p.projects || []).length > 1 ? `<label class="model-pick" title="The codebase the assistant reads. Switching starts a new chat.">
          <span class="muted small">Project</span><select id="project-pick" class="input sm">${p.projects.map((k) =>
            `<option value="${esc(k)}" ${k === currentProject(p) ? "selected" : ""}>${esc(projectName(k))}</option>`).join("")}</select></label>` : ""}
        <label class="model-pick" title="Models your level allows. The gateway enforces the same list on your key.">
          <span class="muted small">Model</span><select id="model-pick" class="input sm">${(p.models || []).map((m) =>
            `<option value="${esc(m)}" ${m === currentModel(p) ? "selected" : ""}>${esc(modelLabel(m))}</option>`).join("")}</select></label>
        <button class="btn sm ghost" data-action="chat-history" title="Chats saved in this browser">${icon("clock")} History</button>
        <button class="btn sm ghost" data-action="new-chat">${icon("plus")} New chat</button></div>
      <div class="messages" id="messages" aria-live="polite"></div>
      <div class="composer">
        <div class="box"><textarea id="q" rows="1" placeholder="Ask about ${esc(projectName(currentProject(p)))}…" aria-label="Message"></textarea>
          <button class="btn primary icon" id="send" data-action="send" aria-label="Send">${icon("send")}</button></div>
        <div class="hint"><span>Enter to send · Shift+Enter for a new line</span><span>${esc(p.agent_model)} through the model gateway, on ${esc(first(p.name))}'s own key</span></div>
      </div>
    </section>
    <aside class="rail" id="rail" aria-label="Your access"></aside></div>`;
  $("#model-pick")?.addEventListener("change", (e) => { (S.model ||= {})[p.id] = e.target.value; });
  $("#project-pick")?.addEventListener("change", (e) => switchProject(p.id, e.target.value));
  const q = $("#q");
  q.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } });
  q.addEventListener("input", () => { q.style.height = "auto"; q.style.height = Math.min(180, q.scrollHeight) + "px"; });
  renderMessages(); renderRail();
  q.focus();
}

function renderMessages() {
  const box = $("#messages");
  if (!box) return;
  const p = me(), msgs = S.chats[S.me] || [];
  if (!msgs.length && S.restoring?.[S.me]) {
    box.innerHTML = `<div class="welcome"><div class="working"><span class="spinner"></span> Loading your last chat…</div></div>`;
  } else if (!msgs.length) {
    const proj = currentProject(p), firstround = proj === Object.keys(S.info.projects || {})[0];
    const prompts = firstround ? [...(PROMPTS[S.me] || []), ...(p.level === "suggest" && S.me !== "leo" ? SUGGEST_EXTRA : [])]
      : PROJECT_PROMPTS[proj] || PROJECT_PROMPTS.screener;
    box.innerHTML = `<div class="welcome"><div class="mark">${logo(22)}</div>
      <h2>Ask anything about ${esc(projectName(proj))}</h2>
      <p>Every answer cites the exact lines it used, and RoleSpace checks each citation against commit
        <span class="mono">${esc(projectCommit(proj).slice(0, 7))}</span> of <span class="mono">${esc(projectRepo(proj))}</span>. ${esc(LEVEL_TEXT[p.level])}</p>
      <div class="suggestions">${prompts.map((t) => `<button class="suggestion" data-action="prompt" data-text="${esc(t)}">${icon("message")}<span>${esc(t)}</span></button>`).join("")}</div></div>`;
  } else {
    box.innerHTML = msgs.map(renderMsg).join("");
    box.scrollTop = box.scrollHeight;
  }
  const busy = !!S.busy[S.me];
  if ($("#send")) $("#send").disabled = busy;
  if ($("#q")) $("#q").placeholder = busy ? "Working on your last question…" : `Ask about ${projectName(currentProject(p))}…`;
}

function citationChip(c) {
  const range = `${c.path}:${c.start}${c.end !== c.start ? "–" + c.end : ""}`;
  return c.ok
    ? `<a class="cite" href="${esc(c.url)}" target="_blank" rel="noopener" title="Verified: the agent read these lines at this commit">${esc(range)}</a>`
    : `<span class="cite-bad" title="Struck out: ${esc(c.reason)}">${esc(range)}</span>`;
}

function md(text, citations) {
  let h = esc(text);
  const groups = {};
  (citations || []).forEach((c) => (groups[esc(c.text)] ||= []).push(c));
  // Longest first, so "[a.mjs:1-20]" isn't split by a shorter bracket inside the same text.
  Object.keys(groups).sort((a, b) => b.length - a.length).forEach((raw) => { h = h.split(raw).join(groups[raw].map(citationChip).join("")); });
  h = h.replace(/`([^`]+)`/g, "<code>$1</code>")
       .replace(/(^|[\s(>])\*\*(\S[^*]*?\S|\S)\*\*/gm, "$1<b>$2</b>")
       .replace(/(^|[\s(])\*([^*\s][^*]*?)\*(?=[\s).,;:!?]|$)/gm, "$1<i>$2</i>");
  // Lists nest by indentation, so "Scoring breakdown:" keeps its sub-bullets under it.
  const out = [], stack = [];
  const closeAll = () => { while (stack.length) out.push(`</li></${stack.pop().kind}>`); };
  for (const line of h.split("\n")) {
    const li = line.match(/^(\s*)([*-]|\d+[.)])\s+(.*)/), hd = line.match(/^#{1,4}\s+(.*)/);
    if (li) {
      const indent = li[1].replace(/\t/g, "    ").length, kind = /\d/.test(li[2]) ? "ol" : "ul";
      while (stack.length && indent < stack.at(-1).indent) out.push(`</li></${stack.pop().kind}>`);
      const top = stack.at(-1);
      if (!top || indent > top.indent) { out.push(`<${kind}>`); stack.push({ kind, indent }); }
      else { out.push("</li>"); if (top.kind !== kind) { out.push(`</${top.kind}><${kind}>`); top.kind = kind; } }
      out.push(`<li>${li[3]}`);
      continue;
    }
    if (!line.trim()) continue;  // a blank line between items keeps the list going
    closeAll();
    out.push(hd ? `<h4>${hd[1]}</h4>` : `<p>${line}</p>`);
  }
  closeAll();
  return out.join("");
}

function whySteps(why) {
  return `<div class="why">${why.steps.map((s) => `<div class="s"><span class="${s.ok ? "ok" : "no"}">${icon(s.ok ? "check" : "x")}</span>
    <span>${esc(s.check)} <span class="muted">· ${esc(s.layer)}</span></span><span class="rule">${esc(s.rule)}</span></div>`).join("")}
    <div class="small muted">Policy version <span class="mono">${esc(why.policy_version)}</span></div></div>`;
}

function aiShell(inner, p, extra = "") {
  return `<div class="msg-ai"><div class="mark">${logo(14)}</div><div>
    <div class="head"><b>RoleSpace</b><span class="lvl ${p.level}">${p.level}</span>${extra}</div>${inner}</div></div>`;
}

function renderMsg(m, i) {
  const p = me();
  if (m.me) return `<div class="msg-me">${esc(m.text)}</div>`;
  if (m.pending) return aiShell(`<div class="working"><span class="spinner"></span> Reading the code through the gateway on
    ${esc(first(p.name))}'s key · <span data-since="${m.started}">0 s</span></div>`, p);
  if (m.error != null) return aiShell(`<div class="callout bad">${icon("alert")}<div><b>${esc(m.error)}</b>
    <div class="row"><button class="btn sm" data-action="prompt" data-text="${esc(m.retry)}">${icon("refresh")} Try again</button></div></div></div>`, p);
  const r = m.r, ok = r.citations.filter((c) => c.ok).length, n = r.citations.length;
  let h = "";
  if (r.blocked) {
    h += `<div class="callout bad">${icon("ban")}<div><b>${esc(r.blocked.message)}</b>${r.blocked.fix ? `<div>${esc(r.blocked.fix)}</div>` : ""}
      <div class="row"><button class="btn sm" data-action="why-blocked" data-model="${esc(r.model)}">${icon("help")} Why was this blocked?</button></div>
      <div class="why-slot"></div></div></div>`;
  }
  if (r.empty) h += `<div class="callout warn">${icon("alert")}<div><b>The assistant finished without an answer.</b> Try rephrasing the question.</div></div>`;
  h += `<div class="answer">${md(r.answer, r.citations)}</div>`;
  r.trace.forEach((t) => {
    if (t.tool === "draft_request" && t.request_id) {
      const owner = S.info.people.find((x) => x.id === t.owner);
      const canElevate = (p.elevation_targets || []).length && !p.grant;
      h += `<div class="callout info">${icon("inbox")}<div><b>Request sent to the owning team.</b>
        ${owner ? `${esc(owner.name)} (${esc(owner.title)}) has it in their inbox.` : "It is waiting in the team's inbox."} Nothing in the code changed.
        <div class="row"><a class="btn sm" href="#/requests">${icon("inbox")} View request</a>
        <button class="btn sm" data-action="why-tool">${icon("help")} Why?</button>
        ${canElevate ? `<button class="btn sm" data-action="request-access">${icon("zap")} Ask for temporary ${esc(cap(p.elevation_targets[0]))} access</button>` : ""}</div>
        <div class="why-slot"></div></div></div>`;
    }
    if (t.flag === "denied" && t.why) {
      h += `<div class="callout bad">${icon("ban")}<div><b>Denied by policy.</b> ${esc(t.why.rule || t.why.decided_by)}. No change was made, and the attempt is in the audit log.
        <details class="steps"><summary>${icon("chevron")} Why: the checks, in order</summary>${whySteps(t.why)}</details></div></div>`;
    }
    if (t.flag === "injection") {
      h += `<div class="callout warn">${icon("shield")}<div><b>Prompt injection ignored.</b> ${esc(t.summary.replace("instruction-like text in", "Instructions aimed at an AI were found in"))}. They were treated as data, not followed, and logged.</div></div>`;
    }
  });
  (r.edits || []).forEach((e) => { h += renderDiff(e); });
  const verified = n ? (ok === n ? `<span class="badge ok">${icon("check")} ${ok}/${n} citations verified</span>`
    : `<span class="badge warn">${icon("alert")} ${ok}/${n} verified · ${n - ok} struck out</span>`) : "";
  h += `<div class="provenance">${verified}<span>${esc(r.model)} via gateway</span><span class="sep"></span><span>${r.seconds ?? "–"} s</span>
    <span class="sep"></span><span class="mono">@${esc((r.commit || S.info.commit).slice(0, 7))}</span></div>`;
  const files = {};
  r.citations.filter((c) => c.ok).forEach((c) => { (files[c.path] ||= { url: c.url.split("#")[0], n: 0 }).n++; });
  if (Object.keys(files).length) h += `<div class="sources">${Object.entries(files).map(([f, v]) =>
    `<a class="source" href="${esc(v.url)}" target="_blank" rel="noopener">${icon("file")} ${esc(f)} <span class="muted">${v.n}</span></a>`).join("")}</div>`;
  if (r.trace.length) h += `<details class="steps"><summary>${icon("chevron")} What the agent did · ${r.trace.length} steps</summary><ol class="timeline">${
    r.trace.map((t) => `<li class="${t.flag || ""}"><code>${esc(t.tool)}</code> ${t.url ? `<a href="${esc(t.url)}" target="_blank" rel="noopener">${esc(t.summary)}</a>` : esc(t.summary)}</li>`).join("")}</ol></details>`;
  return aiShell(h, { ...p, level: r.level }, `<span>${esc(m.at || "")}</span>`);
}

function renderDiff(e) {
  const lines = e.diff.split("\n").filter((l, i, a) => i < a.length - 1 || l);
  const plus = lines.filter((l) => l.startsWith("+") && !l.startsWith("+++")).length;
  const minus = lines.filter((l) => l.startsWith("-") && !l.startsWith("---")).length;
  const body = lines.filter((l) => !l.startsWith("+++") && !l.startsWith("---")).map((l) =>
    `<span class="${l.startsWith("+") ? "add" : l.startsWith("-") ? "del" : l.startsWith("@@") ? "hunk" : ""}">${esc(l) || " "}</span>`).join("");
  const action = e.pr ? `<a class="btn sm" href="${esc(e.pr)}" target="_blank" rel="noopener">${icon("pr")} View pull request ${icon("external")}</a>`
    : e.discarded ? `<span class="badge">Discarded</span>`
    : e.expired ? `<span class="badge" title="Previews live on the server until it restarts. Ask for the edit again to get a new one.">Preview expired · ask again</span>`
    : `<button class="btn sm ghost" data-action="discard" data-id="${esc(e.id)}">Discard</button>
       <button class="btn sm primary" data-action="open-pr" data-id="${esc(e.id)}">${icon("pr")} Open pull request</button>`;
  return `<div class="diff"><div class="diff-head">${icon("file")}<span class="path">${esc(e.path)}</span>
    <span class="plus">+${plus}</span><span class="minus">−${minus}</span><span class="spacer"></span>${action}</div><pre>${body}</pre></div>`;
}

async function send(text) {
  const who = S.me;
  if (S.busy[who]) return;
  const q = (text ?? $("#q")?.value ?? "").trim();
  if (!q) return;
  const msgs = (S.chats[who] ||= []);
  msgs.push({ me: true, text: q }, { pending: true, started: Date.now() });
  S.busy[who] = true;
  if (text == null && $("#q")) { $("#q").value = ""; $("#q").style.height = "auto"; }
  if (S.me === who) renderMessages();
  const slot = msgs.length - 1;
  try {
    const pw = S.info.people.find((x) => x.id === who);
    msgs[slot] = { r: await api("/api/chat", { person: who, message: q, model: currentModel(pw), project: currentProject(pw), chat: chatId(who) }),
                   at: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) };
    const r = msgs[slot].r, proj = S.info.projects?.[r.project];
    if (proj && r.commit && proj.commit !== r.commit) {   // main moved: the answer read the newer commit
      proj.commit = r.commit;
      if (S.me === who && $(".chip.repo")) $(".chip.repo").outerHTML = repoChip();
    }
  } catch (e) {
    msgs[slot] = { error: e.message, retry: q };
  }
  S.busy[who] = false;
  if (S.me === who && S.route === "assistant") { renderMessages(); renderRail(); }
  if (S.me === who) refreshRequestCount();
}

async function renderRail() {
  const rail = $("#rail");
  if (!rail) return;
  const p = me(), who = p.id, all = Object.keys(TOOL_LABELS);
  const grant = p.grant ? `<div class="callout info" style="margin:10px 0 0">${icon("zap")}<div><b>Temporary ${esc(cap(p.level))} access</b>
    until ${clock(p.grant.expires_at)}, approved by ${esc(S.info.people.find((x) => x.id === p.grant.approved_by)?.name || p.grant.approved_by)}.
    Then back to ${esc(cap(p.base_level))}.</div></div>` : "";
  const elevate = (p.elevation_targets || []).length && !p.grant;
  rail.innerHTML = `
    <section class="panel access"><div class="panel-head"><h2>Your access</h2><span id="key-state"></span></div>
      <div class="panel-body">
        <div style="display:flex;gap:10px;align-items:center"><span class="avatar ${p.level}">${esc(p.name.split(" ").map((w) => w[0]).join(""))}</span>
          <div style="min-width:0"><b style="color:var(--ink)">${esc(p.name)}</b><div class="small muted">${esc(p.title)} · ${esc(p.team)}</div></div>
          <span class="lvl ${p.level}" style="margin-left:auto">${p.level}</span></div>
        <p class="small muted" style="margin:10px 0 0">${esc(LEVEL_TEXT[p.level])}</p>${grant}
      </div>
      <div class="panel-body section"><ul class="caps">${all.map((t) => { const y = p.tools.includes(t);
        return `<li class="${y ? "yes" : "no"}">${icon(y ? "check" : "x")}<span>${TOOL_LABELS[t]}</span></li>`; }).join("")}
        <li class="${p.level === "build" ? "yes" : "no"}">${icon(p.level === "build" ? "check" : "x")}<span>Private dev workspace</span></li></ul>
        ${p.allow_paths.length ? (S.info.projects?.[currentProject(p)]?.pull_requests
          ? `<p class="small muted" style="margin:12px 0 0">May edit only ${p.allow_paths.map((a) => `<code>${esc(a)}</code>`).join(" ")}</p>`
          : `<p class="small muted" style="margin:12px 0 0">Edits open as pull requests only in ${esc(projectName(Object.keys(S.info.projects).find((k) => S.info.projects[k].pull_requests)))}. Here, changes go to the owning team as a request.</p>`) : ""}</div>
      <div class="panel-body section" id="budget"><div class="skeleton" style="width:60%"></div><div class="skeleton" style="margin-top:10px"></div></div>
      ${elevate ? `<div class="panel-body section"><b style="color:var(--ink);font-size:13px">Need more access?</b>
        <p class="small muted" style="margin:4px 0 10px">Ask for ${esc(cap(p.elevation_targets[0]))} for a few hours. An admin approves; it ends by itself.</p>
        <button class="btn sm" data-action="request-access">${icon("zap")} Request ${esc(cap(p.elevation_targets[0]))} access</button></div>` : ""}
      ${p.level === "build" ? `<div class="panel-body section"><a class="btn sm" href="#/workspace">${icon("terminal")} Open workspace guide</a></div>` : ""}
      <div class="panel-foot">${icon("lock")} Enforced in code and at the gateway, not by the prompt.</div></section>`;
  try {
    const k = await api("/api/me?person=" + who);
    if (who !== S.me || !$("#budget")) return;
    const pct = k.budget ? Math.min(100, (100 * k.spent) / k.budget) : 0;
    $("#key-state").innerHTML = k.blocked ? `<span class="badge bad">${icon("power")} Suspended</span>` : `<span class="badge ok">Active</span>`;
    $("#budget").innerHTML = `<div class="small muted" style="margin-bottom:4px">AI budget</div><div><span class="big">${money(k.spent)}</span> <span class="muted">of ${money(k.budget)}</span></div>
      <div class="meter ${pct >= 100 ? "bad" : pct >= 80 ? "warn" : ""}" style="margin:10px 0 12px"><i style="width:${pct}%"></i></div>
      <dl class="kv"><dt>Models</dt><dd>${k.models.map((m) => `<code>${esc(m)}</code>`).join(" ")}</dd>
        <dt>Period</dt><dd>${esc(S.info.budget_period)}${k.budget_reset_at ? `, resets ${esc(when(k.budget_reset_at))}` : ""}</dd></dl>`;
  } catch (e) {
    if (who === S.me && $("#budget")) $("#budget").innerHTML = `<span class="small muted">Gateway unavailable: ${esc(e.message)}</span>`;
  }
}

function requestAccess() {
  const p = me(), targets = p.elevation_targets || [], maxH = S.info.elevation?.max_hours || 8;
  if (!targets.length) return;
  modal({
    title: "Request temporary access", sub: `A Govern admin approves it. It ends by itself, and every step is in the audit log.`,
    confirm: "Send request",
    body: `<label class="field">Level<select class="input" name="level">${targets.map((t) => `<option value="${esc(t)}">${esc(cap(t))} · ${esc(LEVEL_TEXT[t])}</option>`).join("")}</select></label>
      <label class="field">For how long<select class="input" name="hours">${[1, 2, 4, 8].filter((h) => h <= maxH).map((h) => `<option value="${h}" ${h === 2 ? "selected" : ""}>${h} hour${h > 1 ? "s" : ""}</option>`).join("")}</select></label>
      <label class="field">Why <span class="hint">The approver sees this.</span><textarea class="input" name="reason" rows="3" maxlength="300" placeholder="e.g. Fix the typo on the landing page before the client demo"></textarea></label>`,
    onConfirm: async (f) => {
      const reason = String(f.get("reason") || "").trim();
      if (reason.length < 3) { toast("Add a short reason for the approver.", "bad"); return false; }
      await api("/api/requests/access", { person: S.me, level: f.get("level"), hours: Number(f.get("hours")), reason });
      toast("Request sent. You'll see the new level as soon as it's approved.");
      refreshRequestCount();
    },
  });
}

// ---- Requests ------------------------------------------------------------------------------

const STATUS = {
  open: ["info", "Open"], in_progress: ["info", "In progress"], done: ["ok", "Done"], declined: ["", "Declined"],
  cancelled: ["", "Withdrawn"], pending: ["warn", "Awaiting approval"], approved: ["ok", "Active"], denied: ["bad", "Denied"],
  expired: ["", "Expired"], revoked: ["", "Ended early"],
};
const ACTION_LABEL = { accept: "Accept", done: "Mark done", decline: "Decline", cancel: "Withdraw", approve: "Approve",
  deny: "Deny", revoke: "End now" };

async function renderRequests(page, id) {
  const p = me();
  S.reqFilter ||= "open";
  page.innerHTML = `<div class="page-head"><div class="t"><h1>Requests</h1>
    <p>${isGov(p) ? "Every change request and access request across the team." : "Changes your level couldn't make become requests to the team that owns the code. Requests for your teams and your own are here."}</p></div>
    <div class="actions"><div class="seg" role="tablist">${["open", "all"].map((f) => `<button role="tab" class="${S.reqFilter === f ? "on" : ""}" data-action="req-filter" data-f="${f}">${f === "open" ? "Open" : "All"}</button>`).join("")}</div></div></div>
    <section class="panel"><div class="panel-body flush" id="req-table"><div class="panel-body"><div class="skeleton"></div></div></div></section>`;
  let data;
  try { data = await api("/api/requests?person=" + p.id); }
  catch (e) { if (id === S.renderId) $("#req-table").innerHTML = `<div class="empty"><b>Couldn't load requests</b>${esc(e.message)}</div>`; return; }
  if (id !== S.renderId) return;
  const live = ["open", "in_progress", "pending", "approved"];
  const rows = data.requests.filter((r) => S.reqFilter === "all" || live.includes(r.status));
  if (!rows.length) {
    $("#req-table").innerHTML = `<div class="empty"><b>${S.reqFilter === "open" ? "Nothing open" : "No requests yet"}</b>
      When the assistant can't make a change at your level, it sends a request here instead.</div>`;
    return;
  }
  $("#req-table").innerHTML = `<div class="table-wrap"><table class="table"><thead><tr><th>Request</th><th>From</th><th>Owner</th><th>Status</th><th>Updated</th><th></th></tr></thead><tbody>
    ${rows.map((r) => { const [cls, label] = STATUS[r.status] || ["", r.status];
      const statusText = r.status === "approved" && r.expires_at ? `${label} until ${clock(r.expires_at)}` : label;
      return `<tr class="clickable" data-action="req-toggle" data-id="${esc(r.id)}">
        <td><div style="display:flex;gap:8px;align-items:center">${r.type === "access" ? `<span class="badge">${icon("zap")} Access</span>` : `<span class="badge">${icon("pr")} Change</span>`}
          <b style="font-weight:600">${esc(r.title)}</b></div><div class="hash" style="margin-top:4px">${esc(r.id.slice(0, 8))} · ${esc(r.team)}</div></td>
        <td>${esc(r.from_name)}</td><td>${esc(r.owner_name || "–")}</td>
        <td><span class="badge ${cls}">${esc(statusText)}</span></td><td class="muted" title="${esc(r.updated || r.ts)}">${esc(ago(r.updated || r.ts))}</td>
        <td class="num"><div class="actions" style="justify-content:flex-end">${r.actions.map((a) =>
          `<button class="btn sm ${["approve", "accept", "done"].includes(a) ? "primary" : ["deny", "revoke"].includes(a) ? "danger" : ""}" data-action="req-act" data-id="${esc(r.id)}" data-a="${a}">${ACTION_LABEL[a]}</button>`).join("")}</div></td></tr>
        <tr class="detail" id="req-${esc(r.id)}" hidden><td colspan="6"><div style="white-space:pre-wrap;color:var(--ink)">${esc(r.details)}</div>
          ${r.history?.length ? `<ul class="history">${r.history.map((h) => `<li>${esc(when(h.ts))} · ${esc(S.info.people.find((x) => x.id === h.by)?.name || h.by)} → ${esc((STATUS[h.status] || ["", h.status])[1])}${h.note ? ` · ${esc(h.note)}` : ""}</li>`).join("")}</ul>` : ""}
          <div class="small muted" style="margin-top:6px">Created ${esc(when(r.ts))}</div></td></tr>`; }).join("")}</tbody></table></div>`;
}

async function actOnRequest(el) {
  const { id, a } = el.dataset;
  const run = async (note = "") => {
    await api(`/api/requests/${encodeURIComponent(id)}`, { person: S.me, action: a, note });
    toast({ accept: "Request accepted.", done: "Marked done.", decline: "Request declined.", cancel: "Request withdrawn.",
            approve: "Approved. The new level is live now and ends by itself.", deny: "Request denied.",
            revoke: "Temporary access ended. They're back on their own level." }[a]);
    await refreshPeople();
    if (S.route === "requests") renderRequests($("#page"), S.renderId); else render();
  };
  if (["deny", "decline", "revoke"].includes(a)) {
    modal({ title: `${ACTION_LABEL[a]} this request?`, confirm: ACTION_LABEL[a], danger: true,
      body: `<label class="field">Note <span class="hint">Optional. The requester sees it.</span><input class="input" name="note" maxlength="300"></label>`,
      onConfirm: (f) => run(String(f.get("note") || "")) });
  } else {
    el.disabled = true;
    try { await run(); } catch (e) { toast(e.message, "bad"); el.disabled = false; }
  }
}

// ---- Workspace (Build) ---------------------------------------------------------------------

async function renderWorkspace(page, id) {
  if (!S.status) await refreshStatus();
  if (id !== S.renderId) return;
  const p = me(), s = S.status || {};
  page.innerHTML = `<div class="page-head"><div class="t"><h1>Workspace</h1>
    <p>Your Coder workspace runs on a private VM with no public IP. Gemini CLI inside it uses your own gateway key, so its calls,
      spend and limits are the same as here.</p></div></div>
    <div class="g3"><section class="panel"><div class="panel-head"><h2>Open the ${esc(S.info.company.toLowerCase())} workspace</h2>
      <span class="badge ${s.coder_vm === "RUNNING" ? "ok" : "warn"}">${icon("server")} coder-vm ${esc((s.coder_vm || "unknown").toLowerCase())}</span></div>
      <div class="panel-body"><ol class="numbered">
        <li><b>Start the Identity-Aware Proxy tunnel</b><span>Run <code>coder/tunnel.sh</code>. No VPN: only Google's IAP range can reach ports 22 and 3000, and only for signed-in people.</span></li>
        <li><b>Sign in to Coder</b><span>Open <code>http://localhost:3000</code> and sign in as <code>${esc(p.email)}</code>.</span></li>
        <li><b>Open your workspace</b><span>Each repository has its own buttons: pick the one you want to work on (below).</span></li>
        <li><b>VS Code or Gemini CLI, per repository</b><span>Gemini CLI reaches the gateway through a relay on the VM, on your own key and budget.</span></li></ol>
        <div class="actions" style="margin-top:16px"><a class="btn primary" href="http://localhost:3000" target="_blank" rel="noopener">${icon("external")} Open Coder</a>
          <span class="small muted">Works once the tunnel is running.</span></div></div></section>
      <section class="panel"><div class="panel-head"><h2>Guardrails</h2></div><div class="panel-body"><ul class="caps">
        <li class="yes">${icon("check")}<span>Private subnet, outbound only through Cloud NAT</span></li>
        <li class="yes">${icon("check")}<span>The VM's identity has no Vertex AI role: <code>try-vertex-directly</code> gets 403</span></li>
        <li class="yes">${icon("check")}<span>Every model call is logged under your key and counts against your budget</span></li>
        <li class="yes">${icon("check")}<span>Only Build-level people in role.yaml get a workspace</span></li>
        <li class="yes">${icon("check")}<span>Only the repositories you have access to are cloned</span></li></ul></div></section></div>
    <section class="panel" style="margin-top:16px"><div class="panel-head"><h2>Your repositories <span class="sub">each one is its own folder and its own buttons in Coder</span></h2></div>
      <div class="panel-body"><div class="ws-repos">${(p.projects || []).map((k) => { const name = projectRepo(k).split("/").pop();
        return `<article class="ws-repo"><div class="rc-top"><span class="rc-icon">${icon("branch")}</span><div style="min-width:0"><b>${esc(projectName(k))}</b>
            <a class="small" href="https://github.com/${esc(projectRepo(k))}" target="_blank" rel="noopener">${esc(projectRepo(k))}</a></div></div>
          <div class="small muted">Folder <code>~/projects/${esc(name)}</code></div>
          <div class="apps"><span class="app">${icon("file")} VS Code · ${esc(name)}</span><span class="app">${icon("terminal")} Gemini CLI · ${esc(name)}</span></div>
          <div class="small muted">Cloned and ready. Pushing uses your own GitHub access.</div></article>`; }).join("")}</div></div></section>`;
}

// ---- Govern: Overview ----------------------------------------------------------------------

async function loadGovern(id) {
  const [g, reqs] = await Promise.all([api("/api/govern?person=" + S.me), api("/api/requests?person=" + S.me).catch(() => ({ requests: [] }))]);
  return id === S.renderId ? { g, reqs: reqs.requests } : null;
}

function kpi(label, value, sub, ic) {
  return `<section class="panel kpi"><div class="k">${ic ? icon(ic) : ""}${esc(label)}</div><div class="v">${value}</div><div class="d">${sub}</div></section>`;
}

const POLICY_STOPS = ["refused_change", "edit_denied", "tool_denied", "injection_ignored"];

async function renderOverview(page, id) {
  page.innerHTML = `<div class="page-head"><div class="t"><h1>Overview</h1>
    <p>Spend, safety and impact across the ${esc(S.info.company)} team, live from the gateway's spend log and the audit trail.</p></div>
    <div class="actions"><button class="btn" data-action="refresh">${icon("refresh")} Refresh</button>
      <button class="btn danger" data-action="demo-reset" title="Put the demo back the way it started, for the next person">${icon("refresh")} Reset demo</button>
      <a class="btn" href="/api/govern/evidence?person=${esc(S.me)}&format=json">${icon("download")} Evidence pack</a></div></div>
    <div id="ov"><div class="kpis">${'<section class="panel kpi"><div class="skeleton" style="width:50%"></div><div class="skeleton" style="height:28px;margin-top:10px"></div></section>'.repeat(4)}</div></div>`;
  let d;
  try { d = await loadGovern(id); } catch (e) { if (id === S.renderId) $("#ov").innerHTML = `<div class="callout bad">${icon("alert")}<div><b>${esc(e.message)}</b></div></div>`; return; }
  if (!d) return;
  const { g, reqs } = d, im = g.impact;
  const tot = g.people.reduce((a, p) => ({ spend: a.spend + p.spent, budget: a.budget + (p.budget || 0), calls: a.calls + p.calls, blocked: a.blocked + p.blocked }), { spend: 0, budget: 0, calls: 0, blocked: 0 });
  const stops = g.audit.filter((a) => POLICY_STOPS.includes(a.kind)).length;
  const src = g.sources, openReqs = reqs.filter((r) => ["open", "in_progress", "pending"].includes(r.status)).length;
  $("#ov").innerHTML = `
    <div class="section-label">Spend and control</div>
    <div class="kpis" style="margin-top:12px">
      ${kpi("AI spend", money(tot.spend), `of ${money(tot.budget)} in budgets · ${esc(S.info.budget_period)} period`, "key")}
      ${kpi("Model calls", tot.calls.toLocaleString(), `last 14 days · app ${src.app?.calls || 0} · workspace ${src.workspace?.calls || 0}`, "server")}
      ${kpi("Blocked at the gateway", tot.blocked, "last 14 days · over budget, model not on key, or suspended", "ban")}
      ${kpi("Policy stops", stops, "refusals, denied edits, ignored injections", "shield")}</div>
    <div class="section-label" style="margin-top:24px">Impact${im.since ? ` since ${esc(when(im.since))}` : ""}</div>
    <div class="kpis" style="margin-top:12px">
      ${kpi("Questions answered", im.answers, im.median_seconds != null ? `median ${im.median_seconds} s per answer` : "no answers yet", "message")}
      ${kpi("Developer interruptions avoided", im.interruptions_avoided, `≈ ${im.hours_saved} h, assuming ${im.minutes_per_question} min each (estimate)`, "users")}
      ${kpi("Citations verified", im.citations ? Math.round((100 * im.verified) / im.citations) + "%" : "–", `${im.verified} of ${im.citations} checked against the code`, "check")}
      ${kpi("Requests routed", reqs.length, `${openReqs} open · refusals become handoffs`, "inbox")}</div>
    <div class="g3" style="margin-top:16px">
      <section class="panel"><div class="panel-head"><h2>Daily AI spend <span class="sub">last 14 days, all people</span></h2></div>
        <div class="panel-body">${spendChart(g.daily)}</div></section>
      <section class="panel"><div class="panel-head"><h2>Budget used</h2><a class="small" href="#/people">Manage</a></div>
        <div class="panel-body"><div class="barlist">${g.people.map((p) => budgetRow(p)).join("")}</div></div></section></div>
    <div class="g2" style="margin-top:16px">
      <section class="panel"><div class="panel-head"><h2>By model</h2></div><div class="panel-body flush">${splitTable(g.models, "Model")}</div></section>
      <section class="panel"><div class="panel-head"><h2>By where it ran</h2></div><div class="panel-body flush">${splitTable(g.sources, "Source")}</div>
        <div class="panel-foot">app = Ask and Suggest agents on Cloud Run · workspace = Gemini CLI in Coder</div></section></div>
    <section class="panel" style="margin-top:16px"><div class="panel-head"><h2>Recent activity</h2><a class="small" href="#/audit">Open audit log</a></div>
      <div class="panel-body flush">${auditTable(g.audit.slice(0, 8), false, true)}</div></section>`;
}

function budgetRow(p) {
  const pct = p.budget ? Math.min(100, (100 * p.spent) / p.budget) : 0;
  return `<div><div class="row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
    <span style="display:flex;gap:8px;align-items:center;color:var(--ink)">${esc(p.name)} <span class="lvl ${p.level}">${p.level}</span></span>
    <span class="small" style="font-variant-numeric:tabular-nums;color:var(--ink)">${money(p.spent)} <span class="muted">/ ${money(p.budget)}</span></span></div>
    <div class="meter ${pct >= 100 ? "bad" : pct >= 80 ? "warn" : ""}" role="meter" aria-valuenow="${Math.round(pct)}" aria-valuemin="0" aria-valuemax="100" aria-label="${esc(p.name)} budget used"><i style="width:${pct}%"></i></div>
    <div class="small muted" style="margin-top:4px">${forecast(p)}</div></div>`;
}

function forecast(p) {
  if (p.blocked_key) return `${icon("power")} Suspended`;
  if (!p.per_day) return "No spend in the last 7 days";
  if (p.budget != null && p.spent >= p.budget) return "Budget used up · new calls are blocked";
  return `${money(p.per_day)}/day` + (p.days_left != null ? ` · ~${p.days_left < 1 ? "<1" : Math.round(p.days_left)} day${p.days_left >= 1.5 ? "s" : ""} left at this pace` : "");
}

function splitTable(obj, label) {
  const rows = Object.entries(obj).sort((a, b) => b[1].spend - a[1].spend);
  if (!rows.length) return `<div class="empty">No calls yet</div>`;
  return `<table class="table"><thead><tr><th>${label}</th><th class="num">Calls</th><th class="num">Spend</th></tr></thead><tbody>${
    rows.map(([k, v]) => `<tr><td><code>${esc(k)}</code></td><td class="num">${v.calls}</td><td class="num">${money(v.spend)}</td></tr>`).join("")}</tbody></table>`;
}

// One series, so one colour and no legend; columns at most 24 px, 4 px rounded tops,
// hairline grid, the largest day labelled, every value on hover and in the tooltip.
const dollarTick = (t) => "$" + (t < 1 && t > 0 ? t.toFixed(2) : t.toFixed(t % 1 ? 1 : 0));
function spendChart(days, fmt = money, tick = dollarTick, what = "AI spend") {
  const W = 640, H = 230, L = 44, R = 8, T = 18, B = 26, max = Math.max(...days.map((d) => d.spend), 0);
  const top = niceMax(max), slot = (W - L - R) / days.length, bw = Math.min(24, slot * 0.62);
  const y = (v) => T + (H - T - B) * (1 - v / top);
  const ticks = [0, top / 2, top];
  const col = (x, yy, w, h) => { const r = Math.min(4, h, w / 2);
    return `M${x},${yy + h}V${yy + r}Q${x},${yy} ${x + r},${yy}H${x + w - r}Q${x + w},${yy} ${x + w},${yy + r}V${yy + h}Z`; };
  const peak = days.reduce((a, d, i) => (d.spend > days[a].spend ? i : a), 0);
  return `<div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Daily ${what}, last ${days.length} days, peak ${fmt(max)}">
    ${ticks.map((t) => `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(t)}" y2="${y(t)}"/><text x="${L - 8}" y="${y(t) + 4}" text-anchor="end">${tick(t)}</text>`).join("")}
    ${days.map((d, i) => { const x = L + i * slot + (slot - bw) / 2, h = (H - T - B) - (y(d.spend) - T), lab = new Date(d.day + "T00:00:00Z");
      const short = lab.toLocaleDateString([], { month: "short", day: "numeric", timeZone: "UTC" });
      return `${h > 0.5 ? `<path class="bar" d="${col(x, y(d.spend), bw, h)}"/>` : ""}
        <rect x="${L + i * slot}" y="${T}" width="${slot}" height="${H - T - B}" fill="transparent" tabindex="0" data-tip="${esc(short)}|${fmt(d.spend)}"/>
        ${i % 2 === 1 || i === days.length - 1 ? `<text x="${x + bw / 2}" y="${H - 8}" text-anchor="middle">${esc(short)}</text>` : ""}
        ${i === peak && max > 0 ? `<text x="${x + bw / 2}" y="${y(d.spend) - 6}" text-anchor="middle" style="fill:var(--ink);font-weight:600">${fmt(d.spend)}</text>` : ""}`; }).join("")}
    </svg></div>`;
}
function niceMax(v) {
  if (v <= 0) return 0.01;
  const p = Math.pow(10, Math.floor(Math.log10(v))), n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
}

// ---- Govern: People & access ---------------------------------------------------------------

async function renderPeople(page, id) {
  page.innerHTML = `<div class="page-head"><div class="t"><h1>People & access</h1>
    <p>Each person's level comes from role.yaml and is enforced on their own gateway key: models, budget, and a kill switch that
      stops every call from the app and their workspace at once.</p></div>
    <div class="actions"><button class="btn" data-action="refresh">${icon("refresh")} Refresh</button>
      <button class="btn primary" data-action="onboard">${icon("plus")} Add person</button></div></div>
    <section class="panel"><div class="panel-body flush" id="people-table"><div class="panel-body"><div class="skeleton"></div></div></div></section>
    <section class="panel" style="margin-top:16px"><div class="panel-head"><h2>Temporary access</h2>
      <span class="small muted">Rule: ${esc(Object.entries(S.info.elevation?.allow || {}).map(([a, b]) => `${a} → ${b.join(", ")}`).join("; ") || "none")}, at most ${esc(S.info.elevation?.max_hours ?? 8)} h</span></div>
      <div class="panel-body flush" id="grants"></div></section>`;
  let g;
  try { g = await api("/api/govern?person=" + S.me); }
  catch (e) { if (id === S.renderId) $("#people-table").innerHTML = `<div class="empty"><b>Couldn't load people</b>${esc(e.message)}</div>`; return; }
  if (id !== S.renderId) return;
  $("#people-table").innerHTML = `<div class="table-wrap"><table class="table"><thead><tr><th>Person</th><th>Level</th><th>Models on key</th>
    <th>Spend</th><th>Pace</th><th class="num">Calls</th><th>Status</th><th></th></tr></thead><tbody>
    ${g.people.map((p) => { const pct = p.budget ? Math.min(100, (100 * p.spent) / p.budget) : 0;
      return `<tr><td><div class="person"><span class="avatar ${p.level}">${esc(p.name.split(" ").map((w) => w[0]).join(""))}</span>
        <div><b>${esc(p.name)}</b><small>${esc(p.title)} · ${esc(p.team)}${p.onboarded ? " · added in RoleSpace" : ""}</small></div></div></td>
      <td><span class="lvl ${p.level}">${p.level}</span>${p.grant ? `<div class="small muted" style="margin-top:4px">${icon("zap")} from ${esc(p.base_level)}, until ${clock(p.grant.expires_at)}</div>` : ""}</td>
      <td>${p.models.map((m) => `<code>${esc(m)}</code>`).join(" ")}</td>
      <td><div class="spend"><div class="row"><span>${money(p.spent)}</span><span class="muted">of ${money(p.budget)}</span></div>
        <div class="meter ${pct >= 100 ? "bad" : pct >= 80 ? "warn" : ""}"><i style="width:${pct}%"></i></div></div></td>
      <td class="small muted" style="max-width:200px">${forecast(p)}</td>
      <td class="num">${p.calls}${p.blocked ? `<div class="small" style="color:#b91c1c">${p.blocked} blocked</div>` : ""}${p.failed ? `<div class="small muted">${p.failed} failed</div>` : ""}</td>
      <td>${p.blocked_key ? `<span class="badge bad">${icon("power")} Suspended</span>` : `<span class="badge ok">Active</span>`}</td>
      <td class="num"><div class="actions" style="justify-content:flex-end">
        <button class="btn sm" data-action="budget" data-id="${esc(p.id)}" data-v="${p.budget ?? ""}" data-name="${esc(p.name)}">Budget</button>
        ${p.id === S.me ? "" : p.blocked_key ? `<button class="btn sm" data-action="suspend" data-id="${esc(p.id)}" data-name="${esc(p.name)}" data-s="0">${icon("power")} Restore</button>`
          : `<button class="btn sm danger" data-action="suspend" data-id="${esc(p.id)}" data-name="${esc(p.name)}" data-s="1">${icon("power")} Suspend</button>`}
        ${p.onboarded ? `<button class="btn sm ghost" data-action="remove-member" data-id="${esc(p.id)}" data-name="${esc(p.name)}">Remove</button>` : ""}
      </div></td></tr>`; }).join("")}</tbody></table></div>`;
  $("#grants").innerHTML = g.grants.length ? `<table class="table"><thead><tr><th>Person</th><th>Level</th><th>Ends</th><th>Approved by</th><th>Reason</th><th></th></tr></thead><tbody>${
    g.grants.map((x) => `<tr><td>${esc(S.info.people.find((p) => p.id === x.person)?.name || x.person)}</td>
      <td><span class="lvl ${x.from_level}">${x.from_level}</span> → <span class="lvl ${x.level}">${x.level}</span></td><td>${clock(x.expires_at)}</td>
      <td>${esc(S.info.people.find((p) => p.id === x.approved_by)?.name || x.approved_by)}</td><td class="muted">${esc(x.reason)}</td>
      <td class="num"><button class="btn sm danger" data-action="end-grant" data-id="${esc(x.request_id || "")}" data-person="${esc(x.person)}">End now</button></td></tr>`).join("")}</tbody></table>`
    : `<div class="empty"><b>No temporary access right now</b>Requests for a higher level appear in Requests for approval.</div>`;
}

function editBudget(el) {
  const { id, v, name } = el.dataset;
  modal({ title: `Budget for ${name}`, sub: "Enforced by the gateway on this person's key. New calls are blocked once spend reaches it.",
    confirm: "Save budget",
    body: `<label class="field">Budget in USD <span class="hint">Between $0 and $20 for this demo, per ${esc(S.info.budget_period)} period.</span>
      <input class="input" name="v" type="number" min="0" max="20" step="0.01" value="${esc(v)}" required></label>`,
    onConfirm: async (f) => {
      const val = parseFloat(f.get("v"));
      if (!isFinite(val) || val < 0) { toast("Enter a budget of $0 or more.", "bad"); return false; }
      const r = await api("/api/govern/budget", { person: S.me, target: id, budget_usd: val });
      toast(`Budget for ${name} set to ${money(r.budget_usd)}.`);
      render();
    } });
}

function suspend(el) {
  const { id, name, s } = el.dataset, on = s === "1";
  modal({ title: on ? `Suspend AI access for ${name}?` : `Restore AI access for ${name}?`,
    sub: on ? "Their gateway key is blocked at once: the assistant, pull requests and Gemini CLI in their workspace all stop. Nothing else about them changes."
            : "Their gateway key works again with the same models and budget.",
    confirm: on ? "Suspend access" : "Restore access", danger: on,
    body: `<label class="field">Reason <span class="hint">Recorded in the audit log.</span><input class="input" name="reason" maxlength="300" placeholder="${on ? "e.g. Laptop reported lost" : "e.g. Resolved with IT"}"></label>`,
    onConfirm: async (f) => {
      await api("/api/govern/suspend", { person: S.me, target: id, suspended: on, reason: String(f.get("reason") || "") });
      toast(on ? `${name} is suspended. Their next model call will be refused by the gateway.` : `${name} is active again.`);
      render();
    } });
}

function endGrant(el) {
  const rid = el.dataset.id;
  if (!rid) return toast("This grant has no request to end; it expires on its own.", "bad");
  actOnRequest({ dataset: { id: rid, a: "revoke" }, disabled: false });
}


// ---- models and projects -------------------------------------------------------------------

const modelLabel = (m) => S.info.catalog?.[m]?.label || m;
const projectName = (id) => S.info.projects?.[id]?.name || id || S.info.repo;
const projectRepo = (id) => S.info.projects?.[id]?.repo || S.info.repo;
const projectCommit = (id) => S.info.projects?.[id]?.commit || S.info.commit;
function repoChip() {
  const p = me(), proj = S.route === "assistant" ? currentProject(p) : null, repo = proj ? projectRepo(proj) : S.info.repo;
  const sha = proj ? projectCommit(proj) : S.info.commit;
  return `<a class="chip repo" href="https://github.com/${esc(repo)}/tree/${esc(sha)}" target="_blank" rel="noopener">
    ${icon("branch")} ${esc(repo)} <span class="mono">@${esc(sha.slice(0, 7))}</span></a>`;
}
// Another codebase is another conversation: the model session and the citations are per repository.
async function switchProject(pid, proj) {
  if (S.busy[pid]) { toast("Wait for the current answer first.", "bad"); return render(); }
  (S.project ||= {})[pid] = proj;
  if ((S.chats[pid] || []).length) {
    S.chats[pid] = []; S.chatId[pid] = newChatId();
    api("/api/reset", { person: pid }).catch(() => {});
    toast(`New chat on ${projectName(proj)}. Your earlier chat is in History.`);
  }
  render();
}
function currentModel(p) {
  const pick = S.model?.[p.id];
  return (p.models || []).includes(pick) ? pick : p.agent_model;
}
function currentProject(p) {
  const pick = S.project?.[p.id];
  return (p.projects || []).includes(pick) ? pick : (p.projects || [])[0];
}

// ---- Issues & pull requests, live from GitHub (nobody needs a GitHub account) --------------

const GH_STATE = { open: ["ok", "Open"], merged: ["merged", "Merged"], closed: ["", "Closed"], draft: ["", "Draft"] };

async function renderGitHub(page, id) {
  const p = me(), proj = currentProject(p);
  page.innerHTML = `<div class="page-head"><div class="t"><h1>Issues & pull requests</h1>
      <p>Live from GitHub for the repositories you can access. Pull requests opened from RoleSpace are marked, so
        people without a GitHub account can follow their changes to merge.</p></div>
      <div class="actions">${(p.projects || []).length > 1 ? `<select class="input" id="gh-project" aria-label="Repository">${p.projects.map((k) =>
        `<option value="${esc(k)}" ${k === proj ? "selected" : ""}>${esc(projectName(k))}</option>`).join("")}</select>` : ""}
        <a class="btn" href="https://github.com/${esc(projectRepo(proj))}" target="_blank" rel="noopener">${icon("external")} Open on GitHub</a></div></div>
    <div id="gh"><div class="kpis">${'<section class="panel kpi"><div class="skeleton" style="width:50%"></div><div class="skeleton" style="height:28px;margin-top:10px"></div></section>'.repeat(4)}</div></div>`;
  $("#gh-project")?.addEventListener("change", (e) => { (S.project ||= {})[p.id] = e.target.value; render(); });
  let d;
  try { d = await api(`/api/github?person=${encodeURIComponent(S.me)}&project=${encodeURIComponent(proj)}`); }
  catch (e) { if (id === S.renderId) $("#gh").innerHTML = `<div class="callout bad">${icon("alert")}<div><b>${esc(e.message)}</b></div></div>`; return; }
  if (id !== S.renderId) return;
  const open = d.pulls.filter((x) => x.state === "open"), ours = d.pulls.filter((x) => x.from_rolespace);
  const state = (x) => { const [c, l] = GH_STATE[x.draft && x.state === "open" ? "draft" : x.state] || ["", x.state]; return `<span class="badge ${c}">${icon("pr")} ${l}</span>`; };
  const who = (x) => `<span class="small muted">#${x.number} · ${esc(x.author || "?")} · ${esc(ago(x.updated))}</span>`;
  $("#gh").innerHTML = `<div class="kpis">
      ${kpi("Open issues", d.issues.length, `in ${esc(d.repo)}`, "inbox")}
      ${kpi("Open pull requests", open.length, `${d.pulls.length} recent in all`, "pr")}
      ${kpi("Merged", d.pulls.filter((x) => x.state === "merged").length, "of the recent pull requests", "check")}
      ${kpi("From RoleSpace", ours.length, "opened for people without GitHub", "zap")}</div>
    <div class="g2" style="margin-top:16px">
      <section class="panel"><div class="panel-head"><h2>Pull requests <span class="sub">newest activity first</span></h2></div>
        <div class="panel-body flush">${d.pulls.length ? `<ul class="gh-list">${d.pulls.map((x) => `<li>
          ${state(x)}<div class="gh-main"><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a>
          <div>${who(x)} ${x.from_rolespace ? `<span class="badge info">${icon("zap")} from RoleSpace</span>` : `<span class="mono small muted">${esc(x.branch)}</span>`}</div></div></li>`).join("")}</ul>`
          : `<div class="empty"><b>No pull requests yet</b>Edits opened from the assistant appear here.</div>`}</div></section>
      <section class="panel"><div class="panel-head"><h2>Open issues <span class="sub">newest activity first</span></h2></div>
        <div class="panel-body flush">${d.issues.length ? `<ul class="gh-list">${d.issues.map((x) => `<li>
          <span class="badge ok">${icon("alert")} Open</span><div class="gh-main"><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a>
          <div>${who(x)}${x.comments ? ` <span class="small muted">· ${x.comments} comment${x.comments === 1 ? "" : "s"}</span>` : ""}
            ${x.labels.map((l) => `<span class="gh-label" style="--c:#${esc(l.color)}">${esc(l.name)}</span>`).join("")}</div></div></li>`).join("")}</ul>`
          : `<div class="empty"><b>No open issues</b>New issues on GitHub appear here within a minute.</div>`}</div></section></div>
    <p class="small muted" style="margin-top:12px">${icon("info")} Read live from GitHub, refreshed every minute. Last read ${esc(ago(d.fetched))}.</p>`;
}

// ---- saved chats ----------------------------------------------------------------------------
// The server keeps each chat under this browser's random id and the person, for 30 days after
// it was last used. Another browser on the same persona never sees them.

const newChatId = () => (crypto.randomUUID?.() || String(Math.random()).slice(2) + Date.now()).replace(/[^A-Za-z0-9-]/g, "");
S.chatId = {};   // person id -> id of the chat on screen
S.restoring = {};
const chatId = (pid) => (S.chatId[pid] ||= newChatId());
const hhmm = (iso) => { const t = parseTime(iso); return isNaN(t) ? "" : new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); };

async function openChat(pid, cid) {
  const c = await api(`/api/chats/${encodeURIComponent(cid)}/open`, { person: pid });
  S.chats[pid] = c.turns.flatMap((t) => [{ me: true, text: t.q }, { r: t.r, at: hhmm(t.at) }]);
  S.chatId[pid] = c.id;
  const proj = c.turns.at(-1)?.r?.project;
  if (proj && S.info.projects?.[proj]) (S.project ||= {})[pid] = proj;
}

async function restoreChat(pid) {
  S.restoring[pid] = true;
  let restored = false;
  try {
    const { chats } = await api("/api/chats?person=" + encodeURIComponent(pid));
    if (chats.length && !S.chats[pid]?.length && !S.busy[pid]) { await openChat(pid, chats[0].id); restored = true; }
  } catch { /* history is a convenience: start fresh */ }
  if (!restored && !S.chats[pid]?.length) api("/api/reset", { person: pid }).catch(() => {});
  S.restoring[pid] = false;
  if (S.me === pid && S.route === "assistant") restored ? render() : renderMessages();
}

async function showHistory() {
  const who = S.me;
  let list;
  try { list = await api("/api/chats?person=" + encodeURIComponent(who)); } catch (e) { return toast(e.message, "bad"); }
  const row = (c) => `<div class="chat-row ${c.id === S.chatId[who] ? "on" : ""}" data-row="${esc(c.id)}">
      <button type="button" class="chat-open" data-open="${esc(c.id)}"><b>${esc(c.title || "Untitled chat")}</b>
        <small>${c.project ? `${esc(projectName(c.project))} · ` : ""}${esc(ago(c.updated))} · ${c.turns} question${c.turns === 1 ? "" : "s"}${c.id === S.chatId[who] ? " · on screen" : ""}</small></button>
      <button type="button" class="btn sm ghost icon" data-del="${esc(c.id)}" aria-label="Delete this chat" title="Delete">${icon("x")}</button></div>`;
  modal({ title: "Saved chats", wide: true, confirm: "Close", cancelButton: false, onConfirm: () => {},
    sub: `${me().name}'s chats in this browser only. Each is deleted ${list.keep_days} days after it was last used.`,
    body: list.chats.length ? `<div class="chat-list">${list.chats.map(row).join("")}</div>`
      : `<div class="empty"><b>No saved chats yet</b>Every question and answer is saved here as you go.</div>` });
  const wrap = $$(".backdrop").at(-1);
  wrap.addEventListener("click", async (ev) => {
    const open = ev.target.closest("[data-open]"), del = ev.target.closest("[data-del]");
    if (open) {
      if (S.busy[who]) return toast("Wait for the current answer first.", "bad");
      try { await openChat(who, open.dataset.open); } catch (e) { return toast(e.message, "bad"); }
      $("[data-ok]", wrap).click();
      if (S.me === who) render();   // its project may differ: picker, top bar and prompts follow
    } else if (del) {
      const cid = del.dataset.del;
      del.disabled = true;
      try { await api(`/api/chats/${encodeURIComponent(cid)}/delete`, { person: who }); }
      catch (e) { del.disabled = false; return toast(e.message, "bad"); }
      $(`[data-row="${CSS.escape(cid)}"]`, wrap)?.remove();
      if (cid === S.chatId[who] && !S.busy[who]) {
        S.chats[who] = []; S.chatId[who] = newChatId();
        api("/api/reset", { person: who }).catch(() => {});
        if (S.me === who) renderMessages();
      }
      toast("Chat deleted.");
    }
  });
}

// ---- Changes: pull requests opened for people without GitHub accounts ----------------------

const PR_STATE = { open: ["info", "Open"], merged: ["ok", "Merged"], closed: ["", "Closed"] };
const CHECKS = { passing: ["ok", "Checks passing"], failing: ["bad", "Checks failing"], pending: ["warn", "Checks running"], none: ["", "No checks"] };

async function renderChanges(page, id) {
  const p = me();
  page.innerHTML = `<div class="page-head"><div class="t"><h1>Changes</h1>
    <p>${isGov(p) ? "Every pull request RoleSpace opened for someone." : "Your pull requests."} Nobody needs a GitHub account: RoleSpace
      opens each one for them, the commit is in their name, and the CI check and a human review still decide what merges.</p></div>
    <div class="actions"><button class="btn" data-action="refresh">${icon("refresh")} Refresh</button></div></div>
    <section class="panel"><div class="panel-body flush" id="changes"><div class="panel-body"><div class="skeleton"></div></div></div></section>`;
  let d;
  try { d = await api("/api/changes?person=" + p.id); }
  catch (e) { if (id === S.renderId) $("#changes").innerHTML = `<div class="empty"><b>Couldn't load changes</b>${esc(e.message)}</div>`; return; }
  if (id !== S.renderId) return;
  if (!d.changes.length) {
    $("#changes").innerHTML = `<div class="empty"><b>No pull requests yet</b>Ask the assistant for a change inside your allow-list, review the diff, and click Open pull request.</div>`;
    return;
  }
  $("#changes").innerHTML = `<div class="table-wrap"><table class="table"><thead><tr><th>Change</th>${isGov(p) ? "<th>For</th>" : ""}<th>Status</th><th>Checks</th><th>Review</th><th>Opened</th><th></th></tr></thead><tbody>
    ${d.changes.map((c) => { const [sc, sl] = PR_STATE[c.state] || ["", c.state || "–"]; const [cc, cl] = CHECKS[c.checks] || ["", c.checks || "–"];
      return `<tr><td><b style="font-weight:600">${esc(c.title || c.detail)}</b>${c.number ? `<div class="hash" style="margin-top:4px">#${c.number}</div>` : ""}${c.error ? `<div class="small" style="color:#b91c1c">${esc(c.error)}</div>` : ""}</td>
        ${isGov(p) ? `<td>${esc(c.name)}</td>` : ""}<td><span class="badge ${sc}">${esc(sl)}</span></td><td><span class="badge ${cc}">${esc(cl)}</span></td>
        <td class="small">${esc(c.review || "–")}${c.comments ? ` · ${c.comments} comment${c.comments > 1 ? "s" : ""}` : ""}</td>
        <td class="muted" title="${esc(c.opened)}">${esc(ago(c.opened))}</td>
        <td class="num"><a class="btn sm" href="${esc(c.url)}" target="_blank" rel="noopener">${icon("external")} View</a></td></tr>`; }).join("")}</tbody></table></div>`;
}

// ---- Govern: Usage ---------------------------------------------------------------------------

const tok = (n) => n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? (n / 1e3).toFixed(1) + "K" : String(n || 0);

async function renderUsage(page, id) {
  S.usageDays ||= 14;
  page.innerHTML = `<div class="page-head"><div class="t"><h1>Usage</h1>
    <p>Tokens and cost for every model call, by person, model, project and source, straight from the gateway's log. Limits are
      enforced on each person's key: budget, requests and tokens per minute.</p></div>
    <div class="actions"><div class="seg">${[7, 14, 30].map((n) => `<button class="${S.usageDays === n ? "on" : ""}" data-action="usage-days" data-n="${n}">${n} days</button>`).join("")}</div>
      <a class="btn" href="/api/govern/usage.csv?person=${esc(S.me)}&days=${S.usageDays}">${icon("download")} CSV</a></div></div>
    <div id="usage"><div class="kpis">${'<section class="panel kpi"><div class="skeleton" style="width:50%"></div><div class="skeleton" style="height:28px;margin-top:10px"></div></section>'.repeat(4)}</div></div>`;
  let u;
  try { u = await api(`/api/govern/usage?person=${S.me}&days=${S.usageDays}`); }
  catch (e) { if (id === S.renderId) $("#usage").innerHTML = `<div class="callout bad">${icon("alert")}<div><b>${esc(e.message)}</b></div></div>`; return; }
  if (id !== S.renderId) return;
  const t = u.totals;
  const split = (obj, label, fmt) => `<table class="table"><thead><tr><th>${label}</th><th class="num">Calls</th><th class="num">Tokens in</th><th class="num">Tokens out</th><th class="num">Cost</th></tr></thead><tbody>${
    Object.entries(obj).map(([k, v]) => `<tr><td>${fmt(k)}</td><td class="num">${v.calls}</td><td class="num">${tok(v.prompt_tokens)}</td><td class="num">${tok(v.completion_tokens)}</td><td class="num">${money(v.spend)}</td></tr>`).join("")
    || `<tr><td colspan="5" class="muted">No calls in this window</td></tr>`}</tbody></table>`;
  $("#usage").innerHTML = `
    <div class="kpis">
      ${kpi("Tokens in", tok(t.prompt_tokens), `last ${u.days} days · prompts and code read`, "download")}
      ${kpi("Tokens out", tok(t.completion_tokens), "answers, edits and tool calls", "send")}
      ${kpi("Cost", money(t.spend), `last ${u.days} days, all models`, "key")}
      ${kpi("Model calls", t.calls.toLocaleString(), t.failed ? `${t.failed} blocked or failed` : "none blocked or failed", "server")}</div>
    <section class="panel" style="margin-top:16px"><div class="panel-head"><h2>By person <span class="sub">limits are on each person's key</span></h2></div>
      <div class="panel-body flush"><div class="table-wrap"><table class="table"><thead><tr><th>Person</th><th class="num">Calls</th><th class="num">Tokens in</th>
        <th class="num">Tokens out</th><th class="num">Cost</th><th>Budget this period</th><th>Rate limits</th><th>Models used</th></tr></thead><tbody>
        ${u.people.map((p) => { const pct = p.budget ? Math.min(100, (100 * p.spent_period) / p.budget) : 0;
          return `<tr><td><div class="person"><span class="avatar sm ${p.level}">${esc(p.name[0])}</span><div><b>${esc(p.name)}</b><small>${p.level}</small></div></div></td>
            <td class="num">${p.calls}</td><td class="num">${tok(p.prompt_tokens)}</td><td class="num">${tok(p.completion_tokens)}</td><td class="num">${money(p.spend)}</td>
            <td><div class="spend"><div class="row"><span>${money(p.spent_period)}</span><span class="muted">of ${money(p.budget)}</span></div>
              <div class="meter ${pct >= 100 ? "bad" : pct >= 80 ? "warn" : ""}"><i style="width:${pct}%"></i></div></div></td>
            <td class="small muted">${p.rpm_limit ? `${p.rpm_limit} req/min` : "–"}<br>${p.tpm_limit ? `${tok(p.tpm_limit)} tokens/min` : ""}</td>
            <td class="small">${Object.entries(p.models).map(([m, v]) => `<span class="badge" title="${v.calls} calls">${esc(modelLabel(m))} · ${money(v.spend)}</span>`).join(" ") || '<span class="muted">–</span>'}</td></tr>`; }).join("")}
        </tbody></table></div></div></section>
    <div class="g3" style="margin-top:16px">
      <section class="panel"><div class="panel-head"><h2>Tokens per day <span class="sub">in + out, all models</span></h2></div>
        <div class="panel-body">${tokenChart(u.daily)}</div></section>
      <section class="panel"><div class="panel-head"><h2>By project</h2></div><div class="panel-body flush">${split(u.projects, "Project", (k) => esc(projectName(k)))}</div></section></div>
    <div class="g2" style="margin-top:16px">
      <section class="panel"><div class="panel-head"><h2>By model</h2></div><div class="panel-body flush">${split(u.models, "Model",
        (k) => `${esc(modelLabel(k))}<div class="small muted">${esc(u.catalog?.[k]?.provider || "")}</div>`)}</div></section>
      <section class="panel"><div class="panel-head"><h2>By where it ran</h2></div><div class="panel-body flush">${split(u.sources, "Source", (k) => `<code>${esc(k)}</code>`)}</div>
        <div class="panel-foot">app = the assistant · workspace = Gemini CLI in Coder · each call is tagged by project, source and level</div></section></div>`;
}

function tokenChart(days) {
  return spendChart(days.map((d) => ({ day: d.day, spend: Object.values(d.tokens).reduce((a, b) => a + b, 0) })), tok, tok, "tokens");
}

// ---- Govern: onboarding ------------------------------------------------------------------

function onboard() {
  const L = S.info.levels, teams = Object.keys(S.info.teams || {}), projects = Object.entries(S.info.projects || {});
  const catalog = S.info.catalog || {};
  modal({
    title: "Add a person", wide: true,
    sub: "RoleSpace creates their own gateway key with the models, budget and limits you choose, stores it in Secret Manager, and gives them their level when they sign in with Google.",
    confirm: "Create access",
    body: `<div class="g2" style="gap:12px">
        <label class="field">Work email<input class="input" name="email" type="email" placeholder="name@${esc(S.info.company_domain || "company.com")}" required></label>
        <label class="field">Full name<input class="input" name="name" required></label></div>
      <div class="g2" style="gap:12px">
        <label class="field">Job title<input class="input" name="title" placeholder="e.g. Product manager"></label>
        <label class="field">Team<select class="input" name="team">${teams.map((t) => `<option value="${esc(t)}">${esc(t)}</option>`).join("")}</select></label></div>
      <label class="field">Level<select class="input" name="level" id="ob-level">${Object.keys(L).map((k) => `<option value="${k}">${cap(k)} · ${esc(LEVEL_TEXT[k])}</option>`).join("")}</select></label>
      <div class="field">Projects<div class="checks">${projects.map(([k, v]) => `<label><input type="checkbox" name="projects" value="${esc(k)}" checked> ${esc(v.name)} <span class="muted small">${esc(v.repo)}</span></label>`).join("")}</div></div>
      <div class="field">Models<div class="checks" id="ob-models"></div></div>
      <label class="field">Monthly AI budget (USD) <span class="hint">Enforced by the gateway on their key.</span><input class="input" name="budget" id="ob-budget" type="number" min="0" max="20" step="0.5"></label>
      <div class="plan" id="ob-plan"></div>`,
    onConfirm: async (f) => {
      const body = { person: S.me, email: String(f.get("email") || ""), name: String(f.get("name") || ""), title: String(f.get("title") || ""),
        team: f.get("team"), level: f.get("level"), projects: f.getAll("projects"), models: f.getAll("models"), budget_usd: parseFloat(f.get("budget")) };
      const r = await api("/api/govern/members", body);
      toast(`${body.name} can sign in now.`);
      modal({ title: `${body.name} is set up`, confirm: "Done", body: `<ul class="caps">${r.steps.map((s) => `<li class="yes">${icon("check")}<span>${esc(s)}</span></li>`).join("")}</ul>`, onConfirm: () => {} });
      await refreshPeople(); render();
    },
  });
  const form = $(".modal form"), level = $("#ob-level", form);
  const sync = () => {
    const l = L[level.value];
    $("#ob-models", form).innerHTML = Object.entries(catalog).map(([k, v]) => {
      const inLevel = l.models.includes(k), on = v.status === "enabled";
      return `<label class="${inLevel && on ? "" : "off"}" title="${esc(!on ? v.note || "Not enabled yet" : inLevel ? "" : "Not allowed at this level")}">
        <input type="checkbox" name="models" value="${esc(k)}" ${inLevel && on ? "checked" : "disabled"}> ${esc(v.label)} <span class="muted small">${esc(v.provider)}${!on ? " · not enabled yet" : !inLevel ? " · not at this level" : ""}</span></label>`; }).join("");
    $("#ob-budget", form).value = l.budget_usd;
    plan();
  };
  const plan = () => {
    const fd = new FormData(form), l = L[fd.get("level")], ms = fd.getAll("models");
    $("#ob-plan", form).innerHTML = `<b>What RoleSpace will create</b><ul>
      <li>A gateway key with ${ms.length ? ms.map(modelLabel).join(", ") : "no models"}, ${money(parseFloat(fd.get("budget")) || 0)} per ${esc(S.info.budget_period)}${l.rpm_limit ? `, ${l.rpm_limit} requests and ${tok(l.tpm_limit)} tokens per minute` : ""}, model routes only</li>
      <li>${esc(cap(fd.get("level")))} level: ${l.tools.includes("propose_edit") ? "answers and pull-request edits" : "answers only, no writes"}${l.allow_paths.length ? ` inside ${l.allow_paths.join(", ")}` : ""}</li>
      ${fd.get("level") === "build" ? "<li>A Coder workspace, queued for the private VM</li>" : ""}
      <li>An audit event naming you as the approver</li></ul>`;
  };
  level.addEventListener("change", sync);
  form.addEventListener("input", plan);
  sync();
}

function removeMember(el) {
  const { id, name } = el.dataset;
  modal({ title: `Remove ${name}?`, danger: true, confirm: "Remove access",
    sub: "Their gateway key is blocked at once and they leave RoleSpace. The audit log keeps everything they did.",
    body: "", onConfirm: async () => {
      await api(`/api/govern/members/${encodeURIComponent(id)}/remove`, { person: S.me });
      toast(`${name} no longer has access.`);
      await refreshPeople(); render();
    } });
}

// ---- Govern: Policy ------------------------------------------------------------------------

async function renderPolicy(page, id) {
  const L = S.info.levels, names = Object.keys(L);
  const peopleAt = (lvl) => S.info.people.filter((p) => p.base_level === lvl).map((p) => esc(first(p.name))).join(", ") || "–";
  const yes = (b) => icon(b ? "check" : "x", b ? "yes" : "no");
  page.innerHTML = `<div class="page-head"><div class="t"><h1>Policy</h1>
    <p>One file, <code>role.yaml</code>, decides every level, and admins can change models, budgets and limits right here. The app
      enforces tools and paths; the gateway enforces models and budgets on each person's key. Version <span class="mono">${esc(S.info.policy_version)}</span>.</p></div></div>
    <section class="panel" id="pf" style="margin-bottom:16px"><div class="panel-body"><div class="skeleton"></div></div></section>
    <div class="g2">
      <section class="panel"><div class="panel-head"><h2>Simulate a decision</h2><span class="small muted">Same rules as production</span></div>
        <div class="panel-body"><form id="sim" class="stack" style="gap:12px">
          <div class="g2" style="gap:12px"><label class="field">Person<select class="input" name="target">${S.info.people.map((p) => `<option value="${esc(p.id)}">${esc(p.name)} · ${p.level}</option>`).join("")}</select></label>
          <label class="field">Action<select class="input" name="action" id="sim-action">
            <option value="edit">Edit a file</option><option value="model">Use a model</option><option value="workspace">Open a workspace</option>
            <option value="tool">Use an agent tool</option><option value="admin">Open admin screens</option></select></label></div>
          <label class="field" id="sim-value-field">Value<input class="input" name="value" id="sim-value" list="sim-list" value="lib/score.mjs" autocomplete="off"></label>
          <datalist id="sim-list"></datalist>
          <div><button class="btn primary" type="submit">${icon("play")} Run check</button></div></form>
          <div id="sim-out" style="margin-top:16px"></div></div></section>
      <section class="panel"><div class="panel-head"><h2>Role matrix</h2></div><div class="panel-body flush"><div class="table-wrap">
        <table class="table matrix"><thead><tr><th></th>${names.map((n) => `<th><span class="lvl ${n}">${n}</span></th>`).join("")}</tr></thead><tbody>
          <tr><td>People</td>${names.map((n) => `<td class="small">${peopleAt(n)}</td>`).join("")}</tr>
          <tr><td>Models</td>${names.map((n) => `<td class="small">${L[n].models.filter(isOn).map((m) => esc(modelLabel(m))).join(", ")}</td>`).join("")}</tr>
          <tr><td>Budget</td>${names.map((n) => `<td class="small">${money(L[n].budget_usd)}</td>`).join("")}</tr>
          ${Object.keys(TOOL_LABELS).map((t) => `<tr><td>${TOOL_LABELS[t]}</td>${names.map((n) => `<td>${yes(L[n].tools.includes(t))}</td>`).join("")}</tr>`).join("")}
          <tr><td>Private workspace</td>${names.map((n) => `<td>${yes(n === "build")}</td>`).join("")}</tr>
          <tr><td>Admin screens</td>${names.map((n) => `<td>${yes(n === "govern")}</td>`).join("")}</tr>
        </tbody></table></div></div>
        <div class="panel-foot">Suggest may edit ${(L.suggest?.allow_paths || []).map((a) => `<code>${esc(a)}</code>`).join(", ")} only, and every edit is a pull request with a CI check and one human review.</div></section></div>
    <section class="panel" style="margin-top:16px"><div class="panel-head"><h2>Model catalog <span class="sub">one gateway, many providers; each key decides who may use what</span></h2></div>
      <div class="panel-body flush"><table class="table"><thead><tr><th>Model</th><th>Provider</th><th>Status</th><th>Levels</th></tr></thead><tbody>
      ${Object.entries(S.info.catalog || {}).map(([k, v]) => `<tr><td><b style="font-weight:600">${esc(v.label)}</b><div class="hash">${esc(k)}</div></td>
        <td>${esc(v.provider)}</td><td>${v.status === "enabled" ? '<span class="badge ok">Enabled</span>' : `<span class="badge" title="${esc(v.note || "")}">${v.status === "setup" ? "Needs setup" : "Off · ready"}</span><div class="small muted" style="margin-top:4px;max-width:340px">${esc(v.note || "")}</div>`}</td>
        <td>${Object.entries(L).filter(([, l]) => l.models.includes(k)).map(([n]) => `<span class="lvl ${n}">${n}</span>`).join(" ") || '<span class="muted small">none yet</span>'}</td></tr>`).join("")}
      </tbody></table></div></section>
    <section class="panel" style="margin-top:16px"><div class="panel-head"><h2>role.yaml</h2><span class="hash">sha256 ${esc(S.info.policy_version)}…</span></div>
      <div class="panel-body flush" id="yaml"><div class="panel-body"><div class="skeleton"></div></div></div></section>`;
  const fillList = () => {
    const a = $("#sim-action").value, v = $("#sim-value");
    const opts = a === "edit" ? S.info.files : a === "model" ? Object.keys(S.info.catalog || {}) : a === "tool" ? Object.keys(TOOL_LABELS) : [];
    $("#sim-list").innerHTML = opts.map((o) => `<option value="${esc(o)}">`).join("");
    $("#sim-value-field").hidden = !opts.length;
    if (opts.length && !opts.includes(v.value)) v.value = a === "edit" ? "lib/score.mjs" : opts[opts.length - 1];
  };
  $("#sim-action").addEventListener("change", fillList); fillList();
  $("#sim").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target), out = $("#sim-out");
    out.innerHTML = `<div class="working"><span class="spinner"></span> Checking…</div>`;
    try {
      const r = await api("/api/policy/explain", { person: S.me, target: f.get("target"), action: f.get("action"), value: String(f.get("value") || "") });
      out.innerHTML = `<div class="verdict ${r.allowed ? "ok" : "bad"}"><div class="icon">${icon(r.allowed ? "check" : "ban")}</div>
        <div><b>${r.allowed ? "Allowed" : "Denied"}</b><span class="small muted">${esc(r.allowed ? r.decided_by : `Stopped by ${r.decided_by}`)}${r.rule ? ` · <span class="mono">${esc(r.rule)}</span>` : ""}</span></div></div>${whySteps(r)}`;
    } catch (err) { out.innerHTML = `<div class="callout bad">${icon("alert")}<div>${esc(err.message)}</div></div>`; }
  });
  $("#sim").requestSubmit();  // show a verdict straight away (after the handler exists)
  try {
    const pol = await api("/api/policy?person=" + S.me);
    if (id !== S.renderId) return;
    renderPolicyForm(pol);
    $("#yaml").innerHTML = `<pre class="code">${pol.source.split("\n").map((l) => {
      const e = esc(l), c = e.indexOf("#");
      const body = c >= 0 ? e.slice(0, c) : e, comment = c >= 0 ? `<span class="c">${e.slice(c)}</span>` : "";
      return body.replace(/^(\s*-?\s*)([\w-]+)(:)/, '$1<span class="k">$2</span>$3') + comment; }).join("\n")}</pre>`;
  } catch (e) { if (id === S.renderId) $("#yaml").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}

// ---- Govern: Repo access -------------------------------------------------------------------
// Who may ask about and work on each repository. Search people and repositories, switch access
// per person, review, save. The assistant follows at once; Build workspaces at their next start.

const initials = (name) => String(name || "?").split(" ").map((w) => w[0]).join("").slice(0, 2);
const sameSet = (a, b) => a.length === b.length && a.every((x) => b.includes(x));

async function renderRepoAccess(page, id) {
  page.innerHTML = `<div class="page-head"><div class="t"><h1>Repo access</h1>
      <p>Who can ask about and work on each repository. The assistant follows a change at once; Build workspaces clone the
        new list at their next start.</p></div>
      <div class="actions"><button class="btn" data-action="refresh">${icon("refresh")} Refresh</button></div></div>
    <div class="ra-tools">
      <label class="search">${icon("search")}<input class="input" id="ra-q" type="search" placeholder="Search people by name, email, team or level" autocomplete="off"></label>
      <label class="search narrow">${icon("branch")}<input class="input" id="ra-rq" type="search" placeholder="Filter repositories" autocomplete="off"></label>
    </div>
    <div id="ra"><section class="panel"><div class="panel-body"><div class="skeleton"></div><div class="skeleton" style="margin-top:10px"></div></div></section></div>`;
  let d;
  try { d = await api("/api/govern/access?person=" + S.me); }
  catch (e) { if (id === S.renderId) $("#ra").innerHTML = `<div class="callout bad">${icon("alert")}<div><b>${esc(e.message)}</b></div></div>`; return; }
  if (id !== S.renderId) return;
  S.ra = { d, draft: Object.fromEntries(d.people.map((p) => [p.id, [...p.projects]])) };
  $("#ra-q").addEventListener("input", paintRepoAccess);
  $("#ra-rq").addEventListener("input", paintRepoAccess);
  $("#ra").addEventListener("click", onRepoAccessClick);
  paintRepoAccess();
}

function raVisible() {
  const { d } = S.ra, q = ($("#ra-q")?.value || "").trim().toLowerCase(), rq = ($("#ra-rq")?.value || "").trim().toLowerCase();
  const people = d.people.filter((p) => !q || [p.name, p.email, p.team, p.level, p.title].some((v) => String(v || "").toLowerCase().includes(q)));
  const repos = Object.keys(d.projects).filter((k) => { const v = d.projects[k]; return !rq || [k, v.name, v.repo, v.team].some((x) => String(x || "").toLowerCase().includes(rq)); });
  return { people, repos };
}

function raChanges() {
  const { d, draft } = S.ra, out = [];
  d.people.forEach((p) => {
    const now = draft[p.id], add = now.filter((x) => !p.projects.includes(x)), rem = p.projects.filter((x) => !now.includes(x));
    if (add.length || rem.length) out.push({ id: p.id, name: p.name, add, rem, empty: !now.length });
  });
  return out;
}

function paintRepoAccess() {
  const box = $("#ra");
  if (!box || !S.ra) return;
  const { d, draft } = S.ra, { people, repos } = raVisible(), P = d.projects;
  const holders = (k) => d.people.filter((p) => draft[p.id].includes(k));
  const cards = repos.map((k) => { const v = P[k], hs = holders(k);
    return `<article class="repo-card"><div class="rc-top"><span class="rc-icon">${icon("branch")}</span>
        <div style="min-width:0"><b>${esc(v.name)}</b><a class="small" href="https://github.com/${esc(v.repo)}/tree/${esc(v.commit)}" target="_blank" rel="noopener">${esc(v.repo)}</a></div></div>
      <div class="rc-tags">${v.pull_requests ? `<span class="badge ok">${icon("pr")} Questions + pull requests</span>` : `<span class="badge">${icon("message")} Questions + workspace</span>`}
        <span class="badge">${icon("users")} ${esc(v.team || "no team")}${v.owner ? ` · ${esc(first(S.info.people.find((x) => x.id === v.owner)?.name || v.owner))}` : ""}</span></div>
      <div class="rc-foot"><div class="avatars">${hs.slice(0, 6).map((p) => `<span class="avatar sm ${p.level}" title="${esc(p.name)}">${esc(initials(p.name))}</span>`).join("")}</div>
        <span class="small muted">${hs.length} of ${d.people.length} people · ${v.files} files</span></div>
      <div class="rc-sync"><span class="small muted">${icon("branch")} main at <a class="mono" href="https://github.com/${esc(v.repo)}/commit/${esc(v.commit)}" target="_blank" rel="noopener">${esc(v.commit.slice(0, 7))}</a>
          ${v.checked ? `· checked ${esc(ago(v.checked))}` : "· from the deploy"}</span>
        <button class="btn sm ghost" data-ra-sync="${esc(k)}" title="Fetch the newest main from GitHub now. Answers also check on their own, at most once a minute.">${icon("refresh")} Sync now</button></div>
      <div class="rc-actions"><button class="btn sm ghost" data-ra-all="${esc(k)}" ${people.length ? "" : "disabled"}>${icon("check")} Give ${people.length === d.people.length ? "everyone" : `these ${people.length}`}</button>
        <button class="btn sm ghost" data-ra-none="${esc(k)}" ${people.length ? "" : "disabled"}>${icon("x")} Remove ${people.length === d.people.length ? "everyone" : `these ${people.length}`}</button></div></article>`; }).join("");
  const rows = people.map((p) => { const base = d.people.find((x) => x.id === p.id), custom = !sameSet(draft[p.id], base.default);
    return `<tr><td><div class="person"><span class="avatar ${p.level}">${esc(initials(p.name))}</span><div><b>${esc(p.name)}</b>
        <small>${esc(p.email || p.title)}${p.onboarded ? " · added in RoleSpace" : ""}</small></div></div></td>
      <td><span class="lvl ${p.level}">${p.level}</span></td><td class="small muted">${esc(p.team)}</td>
      ${repos.map((k) => { const on = draft[p.id].includes(k), was = base.projects.includes(k);
        return `<td><button type="button" class="acc ${on !== was ? "changed" : ""}" aria-pressed="${on}" data-ra-toggle="${esc(p.id)}|${esc(k)}"
          aria-label="${esc(p.name)}: ${esc(P[k].name)}">${icon(on ? "check" : "lock")}<span>${on ? "Access" : "No access"}</span></button></td>`; }).join("")}
      <td class="num">${custom ? `<button type="button" class="btn sm ghost" data-ra-reset="${esc(p.id)}" title="Back to role.yaml or onboarding: ${esc(base.default.map((k) => P[k]?.name || k).join(", "))}">Reset</button>` : `<span class="small muted">Default</span>`}</td></tr>`; }).join("");
  const ch = raChanges(), bad = ch.filter((c) => c.empty);
  box.innerHTML = `<div class="repo-cards">${cards || `<div class="empty"><b>No repository matches</b>Try another name.</div>`}</div>
    <section class="panel"><div class="panel-head"><h2>People <span class="sub">${people.length} of ${d.people.length} shown</span></h2>
      <span class="small muted" style="margin-left:auto">${d.changed_by ? `${icon("info")} Last changed by ${esc(S.info.people.find((x) => x.id === d.changed_by)?.name || d.changed_by)}, ${esc(ago(d.changed_at))}` : "Everyone has role.yaml's defaults"}</span></div>
      <div class="panel-body flush"><div class="table-wrap"><table class="table ra-table"><thead><tr><th>Person</th><th>Level</th><th>Team</th>
        ${repos.map((k) => `<th><div class="ra-col"><b>${esc(P[k].name)}</b><span class="mono">${esc(P[k].repo.split("/").pop())}</span></div></th>`).join("")}<th></th></tr></thead>
        <tbody>${rows || `<tr><td colspan="${4 + repos.length}"><div class="empty"><b>No one matches</b>Search by name, email, team or level.</div></td></tr>`}</tbody></table></div></div></section>
    ${ch.length ? `<div class="ra-bar" role="region" aria-label="Unsaved changes">
      <div style="flex:1;min-width:0"><b>${ch.length} ${ch.length === 1 ? "person" : "people"} changed</b>
        <span class="small">${bad.length ? `${icon("alert")} ${esc(bad.map((c) => first(c.name)).join(", "))} would have no repository: give at least one.`
          : esc(ch.map((c) => `${first(c.name)}: ${[...c.add.map((k) => "+" + P[k].name), ...c.rem.map((k) => "−" + P[k].name)].join(", ")}`).join(" · "))}</span></div>
      <button type="button" class="btn sm" data-ra-discard>Discard</button>
      <button type="button" class="btn sm primary" data-ra-save ${bad.length ? "disabled" : ""}>${icon("check")} Review and save</button></div>` : ""}`;
}

function onRepoAccessClick(ev) {
  const t = ev.target.closest("button");
  if (!t || !S.ra) return;
  const { d, draft } = S.ra, order = Object.keys(d.projects), sorted = (xs) => order.filter((k) => xs.includes(k));
  if (t.dataset.raToggle) {
    const [pid, k] = t.dataset.raToggle.split("|"), cur = draft[pid];
    draft[pid] = sorted(cur.includes(k) ? cur.filter((x) => x !== k) : [...cur, k]);
  } else if (t.dataset.raAll || t.dataset.raNone) {
    const k = t.dataset.raAll || t.dataset.raNone;
    raVisible().people.forEach((p) => { draft[p.id] = sorted(t.dataset.raAll ? [...new Set([...draft[p.id], k])] : draft[p.id].filter((x) => x !== k)); });
  } else if (t.dataset.raReset) {
    draft[t.dataset.raReset] = [...d.people.find((p) => p.id === t.dataset.raReset).default];
  } else if (t.hasAttribute("data-ra-discard")) {
    S.ra.draft = Object.fromEntries(d.people.map((p) => [p.id, [...p.projects]]));
  } else if (t.hasAttribute("data-ra-save")) {
    return saveRepoAccess();
  } else if (t.dataset.raSync) {
    return syncRepo(t);
  } else return;
  paintRepoAccess();
}

async function syncRepo(btn) {
  const k = btn.dataset.raSync, name = S.ra.d.projects[k].name;
  btn.disabled = true; btn.innerHTML = `<span class="spinner"></span> Syncing…`;
  try {
    const r = await api(`/api/govern/repos/${encodeURIComponent(k)}/sync`, { person: S.me });
    S.ra.d = { ...S.ra.d, projects: r.projects };
    toast(r.sync.changed ? `${name} is now at ${r.sync.commit.slice(0, 7)} (was ${r.sync.previous.slice(0, 7)}). The next answer uses it.`
      : `${name} is already at the newest main (${r.sync.commit.slice(0, 7)}).`);
    if (S.info.projects?.[k]) S.info.projects[k].commit = r.sync.commit;
    paintRepoAccess();
  } catch (e) { toast(e.message, "bad"); btn.disabled = false; btn.innerHTML = `${icon("refresh")} Sync now`; }
}

function saveRepoAccess() {
  const ch = raChanges(), P = S.ra.d.projects;
  if (!ch.length || ch.some((c) => c.empty)) return;
  modal({ title: "Save repo access?", confirm: "Save access",
    sub: "The assistant follows at once. Build workspaces clone the new list at their next start, after coder/sync_build_keys.sh. It's recorded in the audit log under your name.",
    body: `<div class="plan"><b>What changes</b><ul>${ch.map((c) => `<li><b>${esc(c.name)}</b>: ${[
      ...c.add.map((k) => `<span class="delta add">+ ${esc(P[k].name)}</span>`), ...c.rem.map((k) => `<span class="delta rem">− ${esc(P[k].name)}</span>`)].join(" ")}</li>`).join("")}</ul></div>`,
    onConfirm: async () => {
      const r = await api("/api/govern/access", { person: S.me, people: Object.fromEntries(ch.map((c) => [c.id, S.ra.draft[c.id]])) });
      S.ra = { d: r, draft: Object.fromEntries(r.people.map((p) => [p.id, [...p.projects]])) };
      toast(`Repo access saved for ${ch.length} ${ch.length === 1 ? "person" : "people"}.`);
      paintRepoAccess();
      refreshPeople();
    } });
}

// ---- Govern: Policy form (no YAML needed) -------------------------------------------------
// Each level's models, budget and rate limits, and which models are switched on. Saving stores the
// change on top of role.yaml, pushes it to every person's gateway key and writes an audit event.

const isOn = (m) => (S.info.catalog?.[m]?.status || "enabled") === "enabled";
const PF_FIELDS = [["budget_usd", "Budget per person (USD)", 0.5], ["rpm_limit", "Requests per minute", 1], ["tpm_limit", "Tokens per minute", 1000]];

function renderPolicyForm(pol) {
  const box = $("#pf");
  if (!box) return;
  const L = S.info.levels, names = Object.keys(L), cat = S.info.catalog || {}, lim = pol.limits || {};
  const edited = pol.changed_by ? `Edited in RoleSpace by ${esc(S.info.people.find((x) => x.id === pol.changed_by)?.name || pol.changed_by)}, ${esc(ago(pol.changed_at))}`
    : "Same as role.yaml";
  box.innerHTML = `<div class="panel-head"><h2>Access by level <span class="sub">tick a box, save, and everyone's key follows. No YAML needed</span></h2>
      <span class="small muted" style="margin-left:auto;margin-right:10px">${icon("info")} ${edited}</span>
      <button class="btn sm ghost" type="button" data-pf="sync" title="Write the policy in force to every person's gateway key again (models and limits)">${icon("refresh")} Push to keys</button>
      <button class="btn sm" type="button" data-pf="reset" ${pol.changed_by ? "" : "disabled"}>Reset to role.yaml</button></div>
    <form id="pf-form" class="panel-body flush" novalidate><div class="table-wrap"><table class="table matrix pf">
      <thead><tr><th>Model</th><th>Switched on</th>${names.map((n) => `<th><span class="lvl ${n}">${n}</span></th>`).join("")}</tr></thead><tbody>
      ${Object.entries(cat).map(([k, v]) => { const on = v.status === "enabled", setup = v.status === "setup";
        return `<tr data-model="${esc(k)}" class="${on ? "" : "off"}"><td><b style="font-weight:600">${esc(v.label)}</b>
          <div class="small muted">${esc(v.provider)}</div>${v.note ? `<div class="small muted pf-note">${esc(v.note)}</div>` : ""}</td>
          <td><label class="switch" title="${esc(setup ? "Needs the one-time setup in the note first" : on ? "Switch off for everyone" : "Switch on")}">
            <input type="checkbox" name="on:${esc(k)}" ${on ? "checked" : ""} ${setup ? "disabled" : ""} aria-label="${esc(v.label)} switched on"><i></i></label></td>
          ${names.map((n) => `<td><input type="checkbox" name="lv:${n}:${esc(k)}" ${L[n].models.includes(k) && on ? "checked" : ""} ${on ? "" : "disabled"}
            aria-label="${esc(v.label)} at ${n} level"></td>`).join("")}</tr>`; }).join("")}
      ${PF_FIELDS.map(([f, label, step]) => { const [lo, hi] = lim[f] || [0, 1e9];
        return `<tr class="pf-num"><td><b style="font-weight:600">${label}</b>${f === "budget_usd" ? `<div class="small muted">per ${esc(S.info.budget_period)}; saving a new value resets that level's keys</div>` : ""}</td><td></td>
        ${names.map((n) => `<td><input class="input sm" type="number" name="${f}:${n}" min="${lo}" max="${hi}" step="${step}" value="${esc(L[n][f] ?? "")}" aria-label="${label}, ${n}"></td>`).join("")}</tr>`; }).join("")}
      </tbody></table></div>
      <div class="panel-foot" style="display:flex;align-items:center;gap:12px"><span id="pf-diff" class="small muted" style="flex:1">No unsaved changes.</span>
        <button class="btn sm" type="button" data-pf="undo" disabled>Undo</button>
        <button class="btn sm primary" type="submit" disabled>${icon("check")} Review and save</button></div></form>`;
  const form = $("#pf-form"), save = $("button[type=submit]", form), undo = $("[data-pf=undo]", form);
  const read = () => {
    const fd = new FormData(form), models = {}, levels = {};
    Object.entries(cat).forEach(([k, v]) => { if (v.status !== "setup") models[k] = fd.get("on:" + k) ? "enabled" : "available"; });
    names.forEach((n) => {
      levels[n] = { models: Object.keys(cat).filter((k) => fd.get(`lv:${n}:${k}`)) };
      PF_FIELDS.forEach(([f]) => { const v = parseFloat(fd.get(`${f}:${n}`)); levels[n][f] = f === "budget_usd" ? v : Math.round(v); });
    });
    return { levels, models };
  };
  const changes = (x) => {
    const out = [];
    Object.entries(x.models).forEach(([k, st]) => { if (st !== cat[k].status) out.push(`${cat[k].label} switched ${st === "enabled" ? "on" : "off"}`); });
    names.forEach((n) => {
      const a = x.levels[n], b = L[n], N = cap(n), was = b.models.filter(isOn);
      const add = a.models.filter((m) => !was.includes(m)), rem = was.filter((m) => !a.models.includes(m));
      if (add.length) out.push(`${N}: add ${add.map(modelLabel).join(", ")}`);
      if (rem.length) out.push(`${N}: remove ${rem.map(modelLabel).join(", ")}`);
      if (a.budget_usd !== b.budget_usd) out.push(`${N}: budget ${money(b.budget_usd)} → ${isFinite(a.budget_usd) ? money(a.budget_usd) : "?"}`);
      if (a.rpm_limit !== b.rpm_limit) out.push(`${N}: ${b.rpm_limit} → ${a.rpm_limit} requests/min`);
      if (a.tpm_limit !== b.tpm_limit) out.push(`${N}: ${tok(b.tpm_limit)} → ${tok(a.tpm_limit)} tokens/min`);
    });
    return out;
  };
  const problems = (x) => {
    const out = [];
    names.forEach((n) => {
      if (!x.levels[n].models.length) out.push(`${cap(n)} needs at least one model`);
      PF_FIELDS.forEach(([f, label]) => { const v = x.levels[n][f], [lo, hi] = lim[f] || [0, 1e12];
        if (!isFinite(v) || v < lo || v > hi) out.push(`${cap(n)}: ${label} must be ${lo.toLocaleString()} to ${hi.toLocaleString()}`); });
    });
    return out;
  };
  const sync = () => {
    $$("tr[data-model]", form).forEach((tr) => {   // a switched-off model can't be given to a level
      const k = tr.dataset.model, on = form.elements["on:" + k]?.checked ?? false;
      tr.classList.toggle("off", !on);
      names.forEach((n) => { const c = form.elements[`lv:${n}:${k}`]; c.disabled = !on; if (!on) c.checked = false; });
    });
    const x = read(), ch = changes(x), bad = problems(x);
    save.disabled = !ch.length || bad.length > 0;
    undo.disabled = !ch.length;
    $("#pf-diff").innerHTML = bad.length ? `<span style="color:#b91c1c">${icon("alert")} ${esc(bad[0])}</span>`
      : ch.length ? `<b style="color:var(--ink)">${ch.length} unsaved change${ch.length === 1 ? "" : "s"}:</b> ${esc(ch.slice(0, 3).join("; "))}${ch.length > 3 ? "…" : ""}`
      : "No unsaved changes.";
  };
  form.addEventListener("input", sync);
  form.addEventListener("change", (ev) => {   // switching a model on offers it to the levels that had it in role.yaml
    const m = ev.target.name?.startsWith("on:") && ev.target.checked ? ev.target.name.slice(3) : null;
    if (m) names.forEach((n) => { if (L[n].models.includes(m)) form.elements[`lv:${n}:${m}`].checked = true; });
    sync();
  });
  undo.addEventListener("click", () => renderPolicyForm(pol));
  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const x = read(), ch = changes(x);
    if (!ch.length || problems(x).length) return;
    const affected = S.info.people.length;
    modal({ title: "Save policy changes?", confirm: "Save and update keys",
      sub: `RoleSpace stores this on top of role.yaml, updates the gateway keys of all ${affected} people right away, and records it in the audit log under your name.`,
      body: `<div class="plan"><b>What changes</b><ul>${ch.map((c) => `<li>${esc(c)}</li>`).join("")}</ul></div>`,
      onConfirm: async () => {
        const r = await api("/api/govern/policy", { person: S.me, ...x });
        r.failed.length ? toast(`Saved, but ${r.failed.length} key${r.failed.length === 1 ? "" : "s"} didn't update (${r.failed.join(", ")}). Save again to retry.`, "bad")
          : toast(`Policy saved. ${r.updated.length} gateway keys updated.`);
        await refreshPeople(); render();
      } });
  });
  $("[data-pf=sync]", box)?.addEventListener("click", async (ev) => {
    const btn = ev.currentTarget;
    btn.disabled = true;
    try {
      const r = await api("/api/govern/policy/sync", { person: S.me });
      r.failed.length ? toast(`${r.updated.length} keys updated; ${r.failed.join(", ")} failed. Try again.`, "bad")
        : toast(`All ${r.updated.length} gateway keys match the policy now.`);
    } catch (e) { toast(e.message, "bad"); }
    btn.disabled = false;
  });
  $("[data-pf=reset]", box)?.addEventListener("click", () => modal({ title: "Reset to role.yaml?", danger: true, confirm: "Reset",
    sub: "Drops every change made here. role.yaml alone decides again, and everyone's gateway key goes back to it.",
    body: "", onConfirm: async () => {
      const r = await api("/api/govern/policy/reset", { person: S.me });
      toast(r.changes.length ? `Back to role.yaml: ${r.changes.length} change${r.changes.length === 1 ? "" : "s"} undone.` : "Already the same as role.yaml.");
      await refreshPeople(); render();
    } }));
}

// ---- Govern: Audit log ---------------------------------------------------------------------

const KIND = {
  refused_change: ["bad", "Change refused"], edit_denied: ["bad", "Edit denied"], tool_denied: ["bad", "Tool denied"],
  injection_ignored: ["warn", "Injection ignored"], edit_previewed: ["", "Edit previewed"], pr_opened: ["info", "PR opened"],
  budget_changed: ["", "Budget changed"], access_suspended: ["bad", "Access suspended"], access_restored: ["ok", "Access restored"],
  access_requested: ["", "Access requested"], elevation_granted: ["info", "Elevation granted"], elevation_denied: ["", "Elevation denied"],
  elevation_ended: ["", "Elevation ended"], request_updated: ["", "Request updated"], evidence_exported: ["", "Evidence exported"],
  handoff_drafted: ["", "Handoff drafted"], member_added: ["ok", "Member added"], member_removed: ["", "Member removed"],
  policy_changed: ["info", "Policy changed"], policy_reset: ["", "Policy reset"], policy_synced: ["", "Keys synced"],
  repo_access_changed: ["info", "Repo access changed"], demo_reset: ["warn", "Demo reset"],
};
const kindBadge = (k) => { const [c, l] = KIND[k] || ["", k.replace(/_/g, " ")]; return `<span class="badge ${c}">${esc(l)}</span>`; };

function auditTable(rows, withHash = true, relative = false) {
  if (!rows.length) return `<div class="empty"><b>No events</b>Refusals, denials, approvals and admin actions appear here.</div>`;
  const nm = (id) => S.info.people.find((p) => p.id === id)?.name || id;
  return `<div class="table-wrap"><table class="table"><thead><tr><th>Time</th><th>Event</th><th>Actor</th><th>Detail</th>${withHash ? "<th>Hash</th>" : ""}</tr></thead><tbody>${
    rows.map((a) => `<tr><td class="muted" style="white-space:nowrap" title="${esc(when(a.ts))} · ${esc(a.ts)}">${esc(relative ? ago(a.ts) : when(a.ts))}</td><td>${kindBadge(a.kind)}</td>
      <td style="white-space:nowrap">${esc(nm(a.person))}</td>
      <td>${a.url ? `<a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.detail)}</a>` : esc(a.detail)}</td>
      ${withHash ? `<td class="hash" title="${esc(a.hash || "before the hash chain")}">${a.hash ? esc(a.hash.slice(0, 10)) : "–"}</td>` : ""}</tr>`).join("")}</tbody></table></div>`;
}

async function renderAudit(page, id) {
  page.innerHTML = `<div class="page-head"><div class="t"><h1>Audit log</h1>
    <p>Every refusal, denied edit, ignored injection, approval and admin action. Append-only and hash-chained: each event carries
      the hash of the one before it, so a changed or deleted event shows up below.</p></div>
    <div class="actions"><a class="btn" href="/api/govern/evidence?person=${esc(S.me)}&format=csv">${icon("download")} CSV</a>
      <a class="btn primary" href="/api/govern/evidence?person=${esc(S.me)}&format=json">${icon("download")} Evidence pack</a></div></div>
    <div id="chain"></div>
    <section class="panel" style="margin-top:16px"><div class="toolbar">
      <input class="input grow" id="a-q" placeholder="Search events" aria-label="Search events">
      <select class="input" id="a-kind" aria-label="Event type"><option value="">All events</option>${Object.entries(KIND).map(([k, v]) => `<option value="${k}">${v[1]}</option>`).join("")}</select>
      <select class="input" id="a-who" aria-label="Actor"><option value="">Everyone</option>${S.info.people.map((p) => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("")}</select>
      <span class="small muted" id="a-count"></span></div><div id="a-rows"><div class="panel-body"><div class="skeleton"></div></div></div></section>`;
  let d;
  try { d = await api("/api/govern/audit?person=" + S.me); }
  catch (e) { if (id === S.renderId) $("#a-rows").innerHTML = `<div class="empty"><b>Couldn't load the audit log</b>${esc(e.message)}</div>`; return; }
  if (id !== S.renderId) return;
  const c = d.chain;
  $("#chain").innerHTML = `<div class="verdict ${c.ok ? "ok" : "bad"}" style="background:var(--canvas)"><div class="icon">${icon(c.ok ? "shield" : "alert")}</div>
    <div><b>${c.ok ? "Chain intact" : "Chain broken"}</b><span class="small muted">${c.ok
      ? `${c.checked} events verified${c.legacy ? ` · ${c.legacy} earlier events were written before the chain started` : ""}${c.head ? ` · head <span class="mono">${esc(c.head.slice(0, 16))}</span>` : ""}`
      : `${esc(c.reason)} (event ${esc(c.event)}), after ${c.checked} good events`}</span></div></div>`;
  const draw = () => {
    const q = $("#a-q").value.toLowerCase(), k = $("#a-kind").value, w = $("#a-who").value;
    const rows = d.events.filter((a) => (!k || a.kind === k) && (!w || a.person === w) && (!q || (a.detail + " " + a.kind).toLowerCase().includes(q)));
    $("#a-count").textContent = `${rows.length} of ${d.events.length}`;
    $("#a-rows").innerHTML = auditTable(rows.slice(0, 300));
  };
  ["#a-q", "#a-kind", "#a-who"].forEach((s) => $(s).addEventListener("input", draw));
  draw();
}

// ---- events --------------------------------------------------------------------------------

const ACTIONS = {
  "account-menu": (el) => openAccountMenu(el),
  persona: (el) => { $(".menu")?.remove(); if (el.dataset.id !== S.me) setPersona(el.dataset.id, S.route); },
  send: () => send(),
  prompt: (el) => send(el.dataset.text),
  "new-chat": async () => {
    if (S.busy[S.me]) return toast("Wait for the current answer first.", "bad");
    try { await api("/api/reset", { person: S.me }); S.chats[S.me] = []; S.chatId[S.me] = newChatId(); renderMessages(); $("#q")?.focus(); }
    catch (e) { toast(e.message, "bad"); }
  },
  "chat-history": () => showHistory(),
  "open-pr": async (el) => {
    const id = el.dataset.id, who = S.me;
    el.disabled = true; el.innerHTML = `<span class="spinner"></span> Opening…`;
    try {
      const { url } = await api("/api/open-pr", { person: who, edit_id: id });
      (S.chats[who] || []).forEach((m) => (m.r?.edits || []).forEach((e) => { if (e.id === id) e.pr = url; }));
      toast("Pull request opened. A human reviews and merges it.");
      if (S.me === who) renderMessages();
    } catch (e) { toast(e.message, "bad"); el.disabled = false; el.innerHTML = `${icon("pr")} Open pull request`; }
  },
  discard: async (el) => {
    const id = el.dataset.id, who = S.me;
    await api("/api/discard-edit", { person: who, edit_id: id }).catch(() => {});
    (S.chats[who] || []).forEach((m) => (m.r?.edits || []).forEach((e) => { if (e.id === id) e.discarded = true; }));
    renderMessages();
  },
  "why-blocked": async (el) => {
    const slot = el.closest(".callout").querySelector(".why-slot");
    el.disabled = true;
    try {
      const r = await api("/api/policy/explain", { person: S.me, target: S.me, action: "model", value: el.dataset.model });
      slot.innerHTML = whySteps(r);
    } catch (e) { slot.innerHTML = `<div class="small">${esc(e.message)}</div>`; }
  },
  "request-access": () => requestAccess(),
  "why-tool": async (el) => {
    const slot = el.closest(".callout").querySelector(".why-slot");
    el.disabled = true;
    try { slot.innerHTML = whySteps(await api("/api/policy/explain", { person: S.me, target: S.me, action: "tool", value: "propose_edit", project: currentProject(me()) })); }
    catch (e) { slot.innerHTML = `<div class="small">${esc(e.message)}</div>`; }
  },
  "welcome-start": (el) => { localStorage.rsWelcomed = "1"; $(".backdrop.onboard")?.remove(); if (el.dataset.id !== S.me) setPersona(el.dataset.id); },
  "req-filter": (el) => { S.reqFilter = el.dataset.f; renderRequests($("#page"), S.renderId); },
  "req-toggle": (el, e) => { if (e.target.closest("button, a")) return; const row = $("#req-" + CSS.escape(el.dataset.id)); if (row) row.hidden = !row.hidden; },
  "req-act": (el) => actOnRequest(el),
  refresh: () => render(),
  budget: (el) => editBudget(el),
  suspend: (el) => suspend(el),
  "end-grant": (el) => endGrant(el),
  onboard: () => onboard(),
  "remove-member": (el) => removeMember(el),
  "demo-reset": () => modal({ title: "Reset the demo?", danger: true, confirm: "Reset demo",
    sub: "For the next judge: everything goes back to how the demo started. The audit log keeps a record of the reset and of everything before it.",
    body: `<div class="plan"><b>What happens</b><ul><li>Policy and repo access go back to role.yaml</li>
      <li>Everyone in role.yaml is active again on their level's models and budget, with spend back to $0</li>
      <li>Temporary access ends; people added during the demo are removed and their keys blocked</li>
      <li>Not changed: the gateway's total budget, which nothing in the app can raise</li></ul></div>`,
    onConfirm: async () => {
      const r = await api("/api/govern/demo-reset", { person: S.me });
      r.failed.length ? toast(`Reset, but some steps failed: ${r.failed.join("; ")}`, "bad") : toast("Demo reset. Everything is back to the start.");
      await refreshPeople(); render();
    } }),
  "usage-days": (el) => { S.usageDays = Number(el.dataset.n); renderUsage($("#page"), S.renderId); },
};

document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-action]");
  if (!e.target.closest(".account")) $(".menu")?.remove();
  if (!el || el.disabled) return;
  const fn = ACTIONS[el.dataset.action];
  if (!fn) return;
  if (el.tagName === "BUTTON" || el.tagName === "A") e.preventDefault();
  fn(el, e);
});

// One tooltip for every chart mark with data-tip="label|value".
const tip = document.createElement("div");
tip.className = "tip"; tip.hidden = true;
document.addEventListener("DOMContentLoaded", () => document.body.append(tip));
function showTip(el, x, y) {
  const [label, value] = el.dataset.tip.split("|");
  tip.replaceChildren(Object.assign(document.createElement("b"), { textContent: value }), document.createTextNode(label));
  tip.hidden = false; tip.style.left = x + 12 + "px"; tip.style.top = y - 44 + "px";
}
document.addEventListener("pointermove", (e) => { const el = e.target.closest?.("[data-tip]"); if (el) showTip(el, e.clientX, e.clientY); else tip.hidden = true; });
document.addEventListener("focusin", (e) => { const el = e.target.closest?.("[data-tip]"); if (el) { const b = el.getBoundingClientRect(); showTip(el, b.left + b.width / 2, b.top); } else tip.hidden = true; });

document.addEventListener("DOMContentLoaded", () => boot().catch((e) => {
  $("#app").innerHTML = `<div class="empty" style="margin:auto"><b>RoleSpace couldn't load</b>${esc(e.message)}</div>`;
}));
