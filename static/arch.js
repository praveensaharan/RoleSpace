"use strict";
// Govern > Architecture: the live HLD. Boxes are what is built (solid) or designed only
// (dashed). Calls animate along their real path: person -> app or workspace -> gateway ->
// Gemini; blocked calls stop at the gateway with the reason. Uses $, esc, S, api from app.js.

const LEVEL_VAR = { ask: "--ask", suggest: "--suggest", build: "--build", govern: "--govern" };
const lvlColor = (l) => getComputedStyle(document.documentElement).getPropertyValue(LEVEL_VAR[l] || "--ink").trim();
const CHIP_Y = { maya: 60, leo: 140, ava: 220, sam: 404 };
const BOXES = {
  people: { x: 10, y: 26, w: 212, h: 474, title: "People, by level", tag: "USERS",
    does: "Four made-up FirstRound people. Each has one level from role.yaml: Ask, Suggest, Build or Govern.",
    stops: "No one gets more AI power than their level; Build is the only level with a workspace. A higher level is only ever temporary and approved." },
  iapapp: { x: 236, y: 64, w: 100, h: 120, title: "IAP for the app", tag: "IAP · LB", lines: ["Google", "sign-in", "HTTPS load", "balancer"],
    does: "Google sign-in through Identity-Aware Proxy on an HTTPS load balancer (rolespace.duckdns.org). Cloud Run takes traffic only from the load balancer. Inside, a persona switcher stands in for directory groups.",
    stops: "Nobody without a Google sign-in reaches the app; the run.app URL answers 403. In production, the level comes from the person's directory group instead of a persona." },
  app: { x: 382, y: 84, w: 210, h: 90, title: "RoleSpace app", tag: "CLOUD RUN", sub: "Ask · Suggest (ADK)",
    does: "Web UI, the Ask and Suggest agents, requests and these Govern screens. Each agent gets only its level's tools and calls Gemini with the person's own key.",
    stops: "Ask has no write tool; Suggest edits outside public/css/** and public/**/*.html are denied; citations to lines the agent never read are struck out; file text aimed at an AI is treated as data." },
  gateway: { x: 672, y: 84, w: 220, h: 90, title: "Model gateway", tag: "RS-GATEWAY", sub: "LiteLLM · keys · budgets", focal: true,
    does: "LiteLLM on Cloud Run. Every model call from the app and from workspaces arrives here with a person's key; it logs the cost per person.",
    stops: "Models not on the key (403), anyone over budget, suspended keys (the kill switch), and callers without a Google identity allowed by Cloud Run IAM." },
  gemini: { x: 940, y: 84, w: 120, h: 90, title: "Gemini", tag: "VERTEX AI", sub: "Flash · Pro",
    does: "gemini-flash (3.8 Flash) and gemini-pro (3.1 Pro) on Vertex AI, global endpoint.",
    stops: "Only the gateway's service account has the Vertex AI role. The app and the workspace VM get 403 if they try directly." },
  firestore: { x: 382, y: 262, w: 170, h: 72, title: "Audit log", tag: "FIRESTORE", sub: "hash-chained",
    does: "Every refusal, denied edit, ignored injection, approval, suspension, budget change and PR, with who and when. Each event carries the hash of the one before it.",
    stops: "Nothing silently: each stop leaves a record, and an edited or deleted record breaks the chain." },
  sql: { x: 722, y: 262, w: 160, h: 72, title: "Keys and spend", tag: "CLOUD SQL", sub: "rs-sql · Postgres",
    does: "The gateway's database: virtual keys, budgets and the spend log behind this dashboard.",
    stops: "No authorised networks: reachable only through the Cloud SQL connector from the gateway." },
  secrets: { x: 940, y: 262, w: 120, h: 72, title: "Secrets", tag: "SECRET MGR", sub: "keys · tokens",
    does: "Each person's gateway key, the master key, the GitHub token and Coder passwords.",
    stops: "Keys never appear in code, chat or this screen." },
  tunnel: { x: 236, y: 396, w: 100, h: 82, title: "IAP tunnel", tag: "IAP", lines: ["IAP tunnel", "to Coder", "port 3000"],
    does: "Identity-Aware Proxy tunnels a developer's browser to Coder on port 3000. No VPN.",
    stops: "The VM has no public IP; the firewall admits only Google's IAP range on ports 22 and 3000." },
  coder: { x: 572, y: 404, w: 312, h: 88, title: "Coder workspaces", tag: "CODER-VM", sub: "VS Code · Gemini CLI · relay",
    does: "coder-vm in a private subnet runs each Build person's dev container, with the repo cloned and Gemini CLI on their own key, through gateway-relay.",
    stops: "Only Build-level people get a workspace. The VM's service account has no Vertex AI role, so there is no way to Gemini except the gateway." },
  github: { x: 1098, y: 84, w: 160, h: 90, title: "firstround-demo", tag: "REPO", sub: "CI check · 1 review",
    does: "praveensaharan/firstround-demo. Suggest-level edits arrive as pull requests from rolespace/* branches.",
    stops: "The designer-allowlist check fails bot PRs outside the allow-list; branch protection needs one human review to merge." },
  designed: { x: 382, y: 540, w: 678, h: 56, title: "Designed, not built", tag: "DESIGNED", dashed: true,
    lines: ["Entra ID group sync (SAML, SCIM) · Model Armor · Cloud KMS keys"],
    does: "Production pieces from our design that are not in this prototype.",
    stops: "Would add: groups from the directory instead of role.yaml, prompt-injection scanning before the model, customer-managed keys." },
};
const TOUR = ["people", "iapapp", "app", "gateway", "gemini", "sql", "firestore", "secrets", "tunnel", "coder", "github", "designed"];
const cx = (b) => b.x + b.w / 2;

function archSvg() {
  const B = BOXES, MONO = "JetBrains Mono,ui-monospace,monospace";
  const A = (x1, y1, x2, y2, col = "#6b7280", dash = "") =>
    `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${col}" stroke-width="1.4" ${dash ? `stroke-dasharray="${dash}"` : ""} marker-end="url(#${col === "#3b82f6" ? "ah-acc" : "ah"})"/>`;
  const label = (x, y, t, col = "#6b7280") => `<rect x="${x - t.length * 3.9 - 5}" y="${y - 12}" width="${t.length * 7.8 + 10}" height="17" rx="2" fill="#ffffff"/>
     <text x="${x}" y="${y}" font-size="12" font-family="${MONO}" fill="${col}" text-anchor="middle" letter-spacing=".04em">${t}</text>`;
  const zone = (x, y, w, h, t) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" fill="#f8f9fa" stroke="#e5e7eb"/>
     <text x="${x + 12}" y="${y + 17}" font-size="11" font-family="${MONO}" fill="#6b7280" letter-spacing=".12em">${t}</text>`;
  const box = (id) => {
    const b = B[id]; if (id === "people") return "";
    const stroke = b.focal ? "#101010" : b.dashed ? "#898989" : "#d1d5db";
    const fill = b.focal ? "#101010" : "#ffffff";
    const ink = b.focal ? "#ffffff" : "#111111", sub = b.focal ? "#a1a1aa" : "#6b7280";
    const text = b.lines
      ? b.lines.map((t, i) => `<text x="${cx(b)}" y="${b.y + 40 + i * 17 - (b.lines.length === 1 ? 4 : 0)}" text-anchor="middle" font-size="13" fill="#6b7280" font-family="${MONO}">${esc(t)}</text>`).join("")
      : `<text x="${cx(b)}" y="${b.y + (b.h > 80 ? 50 : 44)}" text-anchor="middle" font-size="16" font-weight="600" fill="${ink}" letter-spacing="-0.3">${esc(b.title)}</text>
         <text x="${cx(b)}" y="${b.y + (b.h > 80 ? 72 : 63)}" text-anchor="middle" font-size="12" fill="${sub}" font-family="${MONO}">${esc(b.sub)}</text>`;
    return `<g class="box" id="box-${id}" data-action="arch-explain" data-id="${id}" tabindex="0" role="button" aria-label="${esc(b.title)}">
      <rect class="frame" x="${b.x}" y="${b.y}" width="${b.w}" height="${b.h}" rx="6" fill="${fill}" stroke="${stroke}"
        stroke-width="${b.focal ? 1.7 : 1.2}" ${b.dashed ? 'stroke-dasharray="6,4"' : ""}/>
      <text x="${b.x + 9}" y="${b.y + 17}" font-size="10.5" font-family="${MONO}" fill="${sub}" letter-spacing=".08em">${b.tag}</text>
      ${text}<circle id="dot-${id}" cx="${b.x + b.w - 12}" cy="${b.y + 13}" r="0"/></g><g id="badges-${id}"></g>`;
  };
  const chips = S.info.people.map((p) => {
    const y = CHIP_Y[p.id] ?? 300, c = lvlColor(p.level);
    return `<g class="box chipbox" id="chip-${p.id}" data-action="arch-explain" data-id="people">
      <rect class="frame" x="22" y="${y}" width="188" height="66" rx="8" fill="#fff" stroke="${c}" stroke-width="1.6"/>
      <rect x="22" y="${y}" width="7" height="66" rx="3" fill="${c}"/>
      <text x="40" y="${y + 22}" font-size="15" font-weight="600" fill="#111111">${esc(p.name.split(" ")[0])}</text>
      <text x="200" y="${y + 22}" font-size="11" font-weight="600" fill="#6b7280" text-anchor="end" letter-spacing=".06em">${p.level.toUpperCase()}${p.grant ? " · TEMP" : ""}</text>
      <rect x="40" y="${y + 31}" width="160" height="7" rx="3.5" fill="#e5e7eb"/><rect id="bar-${p.id}" x="40" y="${y + 31}" width="0" height="7" rx="3.5" fill="${c}"/>
      <text id="spend-${p.id}" x="40" y="${y + 56}" font-size="12" font-family="${MONO}" fill="#6b7280"></text>
      <text id="blk-${p.id}" x="200" y="${y + 56}" font-size="12" font-weight="700" fill="#ef4444" text-anchor="end"></text></g>`;
  }).join("");
  return `<svg viewBox="0 -16 1280 632" xmlns="http://www.w3.org/2000/svg" font-family="Inter,-apple-system,BlinkMacSystemFont,sans-serif" role="img" aria-label="Live architecture">
    <defs><marker id="ah" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#6b7280"/></marker>
      <marker id="ah-acc" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#3b82f6"/></marker></defs>
    ${zone(10, 26, 212, 474, "INTERNET")}
    ${zone(352, 26, 720, 584, "GOOGLE CLOUD · US-CENTRAL1")}
    ${zone(366, 50, 534, 148, "CLOUD RUN")}
    ${zone(556, 372, 344, 132, "PRIVATE SUBNET · NO PUBLIC IP")}
    ${zone(1086, 50, 184, 148, "GITHUB")}
    ${A(210, 124, 236, 124)} ${A(336, 124, 382, 124)}
    ${A(592, 129, 672, 129)} ${A(892, 129, 940, 129, "#111111")}
    ${A(467, 174, 467, 262)} ${A(802, 174, 802, 262)}
    ${A(210, 437, 236, 437)} ${A(336, 437, 572, 437)}
    <path d="M 700,404 V 174" stroke="#6b7280" stroke-width="1.4" fill="none" marker-end="url(#ah)"/>
    <path d="M 487,84 V 8 H 1178 V 84" stroke="#3b82f6" stroke-width="1.5" fill="none" marker-end="url(#ah-acc)"/>
    ${label(632, 121, "OWN KEY")} ${label(916, 121, "ONLY", "#111111")} ${label(467, 240, "AUDIT")} ${label(802, 246, "SPEND")}
    ${label(454, 430, "IAP :3000")} ${label(700, 356, "OWN KEY")} ${label(830, 4, "PULL REQUEST · SUGGEST", "#3b82f6")}
    <text x="1062" y="432" text-anchor="end" font-size="17" font-weight="600" letter-spacing="-0.5" fill="#111111">Only the gateway</text>
    <text x="1062" y="454" text-anchor="end" font-size="17" font-weight="600" letter-spacing="-0.5" fill="#111111">may call Gemini.</text>
    ${chips}
    ${Object.keys(B).map(box).join("")}
    <g id="flights"></g>
  </svg>`;
}

window.renderArch = async function renderArch(page, id) {
  page.innerHTML = `<div class="page-head"><div class="t"><h1>Architecture</h1>
      <p>Who is using what, right now. Calls animate along their real path; blocked calls stop at the gateway with the reason.
        Click any box for what it does and what it stops.</p></div>
    <div class="actions"><span class="chip"><span class="dot live"></span> Live · every 6 s</span>
      <button class="btn" data-action="arch-tour">${icon("play")} Tour</button></div></div>
    <section class="panel arch-wrap">${archSvg()}</section>
    <div class="g2" style="margin-top:16px">
      <section class="panel"><div class="panel-body explain" id="explain"><h4>New here?</h4>
        <p class="muted">Click a box to see what it does and what it stops, or press <b>Tour</b> to walk a request through the platform in order.</p></div></section>
      <section class="panel"><div class="panel-head"><h2>Live calls</h2></div><div class="panel-body" style="padding-top:4px;padding-bottom:4px">
        <ul class="feed" id="feed"><li class="muted">Waiting for calls…</li></ul></div></section></div>`;
  S.arch = { seen: new Set(), audit: new Set(), first: true, id };
  await archTick();
  if (id === S.renderId) S.timers.arch = setInterval(archTick, 6000);
};

async function archTick() {
  const st = S.arch;
  if (!st || st.id !== S.renderId || (document.hidden && !st.first)) return;
  let g;
  try { g = await api("/api/architecture?person=" + S.me); } catch { return; }
  if (st.id !== S.renderId || !$("#feed")) return;  // the admin moved on while we waited
  const nowMs = Date.now();
  g.people.forEach((p) => {
    const pct = p.budget ? Math.min(1, p.spent / p.budget) : 0, bar = $("#bar-" + p.id);
    if (!bar) return;
    bar.setAttribute("width", Math.max(2, 160 * pct));
    bar.setAttribute("fill", p.blocked_key || pct > 0.9 ? "#ef4444" : lvlColor(p.level));
    $("#spend-" + p.id).textContent = `${money(p.spent)} / ${money(p.budget ?? 0)}`;
    $("#blk-" + p.id).textContent = p.blocked_key ? "suspended" : p.blocked ? `${p.blocked} blocked` : "";
    const last = g.recent.filter((c) => c.pid === p.id).map((c) => parseTime(c.time))[0];
    $("#chip-" + p.id).classList.toggle("pulse", !!last && nowMs - last < 60000);
  });
  const dot = (id, ok, title) => { const d = $("#dot-" + id); if (!d) return; d.setAttribute("r", 5);
    d.setAttribute("fill", ok ? "#10b981" : "#ef4444"); d.innerHTML = `<title>${esc(title)}</title>`; };
  dot("gateway", g.health.gateway === "up", "gateway " + g.health.gateway);
  dot("coder", g.health.coder_vm === "RUNNING", "coder-vm " + g.health.coder_vm);
  dot("app", true, "app up");
  const count = (kinds) => g.audit.filter((a) => kinds.includes(a.kind)).length;
  const blocked = g.people.reduce((n, p) => n + p.blocked, 0);
  const newAudit = g.audit.filter((a) => !st.audit.has(a.id || a.ts + a.kind));
  const flash = !st.first;
  badges("app", [["refused", count(["refused_change"]), "#ef4444"], ["denied", count(["edit_denied", "tool_denied"]), "#ef4444"],
    ["injection ignored", count(["injection_ignored"]), "#f59e0b"]], flash && newAudit.some((a) => POLICY_STOPS.includes(a.kind)));
  badges("gateway", [["blocked", blocked, "#ef4444"], ["suspended", g.people.filter((p) => p.blocked_key).length, "#111111"],
    ["budget set", count(["budget_changed"]), "#3b82f6"]], flash && newAudit.some((a) => ["budget_changed", "access_suspended"].includes(a.kind)));
  badges("github", [["PRs", count(["pr_opened"]), "#8b5cf6"]], flash && newAudit.some((a) => a.kind === "pr_opened"));
  badges("firestore", [["events", g.audit.length, "#6b7280"]], flash && newAudit.length > 0);
  g.audit.forEach((a) => st.audit.add(a.id || a.ts + a.kind));
  // calls we haven't seen fly; on first load only those from the last 2 minutes
  const fresh = g.recent.filter((c) => !st.seen.has(c.id)).reverse();
  fresh.forEach((c, i) => {
    st.seen.add(c.id);
    if (!st.first || nowMs - parseTime(c.time) < 120000) setTimeout(() => fly(c), i * 700);
  });
  st.first = false;
  $("#feed").innerHTML = g.recent.slice(0, 8).map((c) => `<li><span class="lvl ${c.level}">${esc(c.person.split(" ")[0])}</span>
    <span class="muted">${esc(c.source)}</span><code>${esc(c.model)}</code>
    ${c.ok ? `<span class="badge ok">ok</span>` : `<span class="badge bad">blocked: ${esc(blockReason(c))}</span>`}
    <span class="muted" style="margin-left:auto">${esc(ago(c.time))}</span></li>`).join("") || `<li class="muted">No calls yet</li>`;
}

function blockReason(c) {
  const e = (c.error || "").toLowerCase();
  if (e.includes("budget")) return "over budget";
  if (e.includes("blocked")) return "key suspended";
  if (e.includes("not available") || e.includes("not allowed")) return "model not on key";
  return c.error ? c.error.slice(0, 40) : "refused by gateway";
}

// Badges hang under the box that enforced them, right-aligned, measured after rendering so
// they never overlap; a row that would run past the box's left edge wraps to a new row.
function badges(id, items, flash) {
  const b = BOXES[id], g = $("#badges-" + id); if (!g) return;
  const list = items.filter(([, n]) => n > 0);
  g.innerHTML = list.map(([t, n, col]) => `<g class="${flash ? "badge-new" : ""}"><rect height="18" rx="9" fill="${col}"/>
    <text font-size="11.5" font-weight="600" fill="${col === "#f59e0b" ? "#111111" : "#ffffff"}" text-anchor="middle">${esc(`${n} ${t}`)}</text></g>`).join("");
  let x = b.x + b.w, y = b.y + b.h + 4;
  [...g.children].reverse().forEach((el) => {
    const text = el.querySelector("text"), w = (text.getComputedTextLength() || 60) + 16;
    if (x - w < b.x - 24 && x < b.x + b.w) { x = b.x + b.w; y += 22; }
    x -= w;
    const rect = el.querySelector("rect");
    rect.setAttribute("x", x); rect.setAttribute("y", y); rect.setAttribute("width", w);
    text.setAttribute("x", x + w / 2); text.setAttribute("y", y + 13);
    x -= 4;
  });
}

function pathFor(c) {
  const y = (CHIP_Y[c.pid] ?? 300) + 33, gw = [782, 129];
  const pts = c.source === "workspace"
    ? [[204, y], [222, y], [222, 437], [336, 437], [572, 437], [700, 437], [700, 174], gw]
    : [[204, y], [222, y], [222, 124], [336, 124], [487, 124], [592, 129], [672, 129], gw];
  return c.ok ? [...pts, [892, 129], [1000, 129]] : pts;
}

function fly(c) {
  const layer = $("#flights"); if (!layer) return;
  const pts = pathFor(c), col = lvlColor(c.level), NS = "http://www.w3.org/2000/svg";
  const seg = pts.slice(1).map((p, i) => Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]));
  const total = seg.reduce((a, b) => a + b, 0), dur = 2600, t0 = performance.now();
  const trail = document.createElementNS(NS, "polyline");
  trail.setAttribute("points", pts.map((p) => p.join(",")).join(" "));
  trail.setAttribute("fill", "none"); trail.setAttribute("stroke", col); trail.setAttribute("stroke-width", "3");
  trail.setAttribute("stroke-opacity", ".35"); trail.setAttribute("stroke-dasharray", `0 ${total}`);
  const dotEl = document.createElementNS(NS, "circle"); dotEl.setAttribute("r", "7"); dotEl.setAttribute("fill", col);
  dotEl.setAttribute("stroke", "#fff"); dotEl.setAttribute("stroke-width", "2");
  layer.append(trail, dotEl);
  const step = (now) => {
    const f = Math.min(1, (now - t0) / dur); let d = f * total, i = 0;
    while (i < seg.length - 1 && d > seg[i]) { d -= seg[i]; i++; }
    const a = pts[i], b = pts[i + 1], k = seg[i] ? d / seg[i] : 0;
    dotEl.setAttribute("cx", a[0] + (b[0] - a[0]) * k); dotEl.setAttribute("cy", a[1] + (b[1] - a[1]) * k);
    trail.setAttribute("stroke-dasharray", `${f * total} ${total}`);
    if (f < 1) return requestAnimationFrame(step);
    if (!c.ok) {  // stopped at the gateway: red, with the reason
      dotEl.setAttribute("fill", "#ef4444");
      const reason = document.createElementNS(NS, "g");
      const t = `✕ ${c.person.split(" ")[0]}: ${blockReason(c)}`, w = t.length * 7.4 + 20;
      reason.innerHTML = `<rect x="${782 - w / 2}" y="204" width="${w}" height="24" rx="12" fill="#ef4444"/>
        <text x="782" y="220" font-size="13" font-weight="700" fill="#fff" text-anchor="middle">${esc(t)}</text>`;
      layer.append(reason); setTimeout(() => reason.remove(), 6000);
    }
    setTimeout(() => { trail.remove(); dotEl.remove(); }, c.ok ? 900 : 6000);
  };
  requestAnimationFrame(step);
}

function archExplain(id) {
  const b = BOXES[id]; if (!b || !$("#explain")) return;
  $$(".box.focus").forEach((e) => e.classList.remove("focus"));
  (id === "people" ? $$(".chipbox") : [$("#box-" + id)]).forEach((e) => e && e.classList.add("focus"));
  const n = TOUR.indexOf(id);
  $("#explain").innerHTML = `<h4>${esc(b.title)} ${b.dashed ? '<span class="badge">Designed, not built</span>' : '<span class="badge ok">Built</span>'}</h4>
    <p><b>Does:</b> ${esc(b.does)}</p><p class="stops"><b>Stops:</b> ${esc(b.stops)}</p>
    ${S.touring ? `<p class="small muted">Tour step ${n + 1} of ${TOUR.length} · <a href="#" data-action="arch-tour-stop">Stop</a></p>` : ""}`;
}

function archTour() {
  archTourStop(); S.touring = true; let i = 0;
  const next = () => {
    if (!S.touring || S.route !== "architecture") return archTourStop();
    archExplain(TOUR[i]); i++;
    S.tourTimer = setTimeout(i < TOUR.length ? next : archTourStop, 4500);
  };
  next();
}
function archTourStop() { S.touring = false; clearTimeout(S.tourTimer); }

Object.assign(ACTIONS, {
  "arch-explain": (el) => archExplain(el.dataset.id),
  "arch-tour": () => archTour(),
  "arch-tour-stop": () => { archTourStop(); const p = $("#explain p.small"); if (p) p.remove(); },
});
document.addEventListener("keydown", (e) => {
  if ((e.key === "Enter" || e.key === " ") && e.target.closest?.(".box[data-action]")) { e.preventDefault(); archExplain(e.target.closest(".box").dataset.id); }
});
