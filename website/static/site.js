/* RoleSpace website: the interactive pieces. Plain JS, no inline handlers (strict CSP).
   Every demo runs on the made-up FirstRound team; numbers marked "measured" come from the
   RoleSpace evaluation, everything else is labelled as an example or an assumption. */
"use strict";
document.documentElement.classList.add("js");

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const REDUCE = matchMedia("(prefers-reduced-motion: reduce)").matches;
const sleep = (ms) => new Promise((r) => setTimeout(r, REDUCE ? 0 : ms));
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const icon = (n, cls = "i") => `<svg class="${cls}" aria-hidden="true"><use href="#i-${n}"/></svg>`;
const fmt = (n) => Math.round(n).toLocaleString("en-US");
const money = (v) => (v >= 1e6 ? `$${(v / 1e6).toFixed(v >= 1e7 ? 0 : 1)}M` : v >= 1e4 ? `$${fmt(v / 1000)}K` : v >= 100 ? `$${fmt(v)}` : `$${v.toFixed(2)}`);
const usd = (n) => (Number.isInteger(n) ? `$${n}` : `$${n.toFixed(2)}`);
const compact = (n) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}K` : fmt(n));

/** Run fn once when el scrolls into view (straight away if observers aren't supported). */
function whenVisible(el, fn, threshold = 0.25) {
  if (!el) return;
  if (!("IntersectionObserver" in window)) return fn();
  const io = new IntersectionObserver((entries) => {
    if (entries.some((e) => e.isIntersecting)) { io.disconnect(); fn(); }
  }, { threshold });
  io.observe(el);
}

// ---- the made-up FirstRound team and policy (mirrors role.yaml) -------------------------------

const PEOPLE = {
  maya: { name: "Maya Chen", first: "Maya", title: "Product manager", level: "ask", init: "MC", key: "maya-ask", budget: 2, spent: 0.62 },
  leo: { name: "Leo Park", first: "Leo", title: "Product designer", level: "suggest", init: "LP", key: "leo-suggest", budget: 2.5, spent: 0.73 },
  sam: { name: "Sam Okafor", first: "Sam", title: "Developer", level: "build", init: "SO", key: "sam-build", budget: 10, spent: 0.14 },
  ava: { name: "Ava Rossi", first: "Ava", title: "Platform admin", level: "govern", init: "AR", key: "ava-govern", budget: 1, spent: 0.02 },
};
const LEVEL = { ask: "Ask", suggest: "Suggest", build: "Build", govern: "Govern" };
const MODELS = [
  { id: "gemini-flash", label: "Gemini 3.8 Flash", provider: "Google", logo: "googlegemini", on: true },
  { id: "gemini-pro", label: "Gemini 3.1 Pro", provider: "Google", logo: "googlegemini", on: true },
  { id: "kimi-k2", label: "Kimi K2 Thinking", provider: "Moonshot AI", logo: "kimi", on: true },
  { id: "qwen-coder", label: "Qwen3 Coder 480B", provider: "Alibaba Qwen", logo: "qwen", on: true },
  { id: "deepseek", label: "DeepSeek V3.2", provider: "DeepSeek", logo: "deepseek", on: false },
  { id: "claude-sonnet", label: "Claude Sonnet", provider: "Anthropic", logo: "claude", on: false },
];
const logo = (id, size = 18) => { const m = MODELS.find((x) => x.id === id);
  return m ? `<img class="mlogo" src="/assets/logos/${m.logo}.svg" alt="" width="${size}" height="${size}">` : ""; };
const LEVEL_MODELS = {
  ask: new Set(["gemini-flash", "kimi-k2"]),
  suggest: new Set(["gemini-flash", "gemini-pro", "kimi-k2", "qwen-coder"]),
  build: new Set(["gemini-flash", "gemini-pro", "kimi-k2", "qwen-coder"]),
  govern: new Set(["gemini-flash"]),
};
const REPOS = [
  { id: "firstround-demo", name: "Screening app" },
  { id: "RoleSpace", name: "RoleSpace" },
  { id: "firstround", name: "Original screener" },
];
const ACCESS = { maya: new Set(["firstround-demo", "firstround"]), leo: new Set(["firstround-demo"]),
                 sam: new Set(["firstround-demo", "RoleSpace", "firstround"]), ava: new Set(["firstround-demo", "RoleSpace", "firstround"]) };
const modelLabel = (id) => MODELS.find((m) => m.id === id)?.label || id;
const keyModels = (pid) => MODELS.filter((m) => m.on && LEVEL_MODELS[PEOPLE[pid].level].has(m.id)).map((m) => m.id);

// ---- nav: shadow on scroll, section highlight, mobile sheet ------------------------------------

(function nav() {
  const bar = $(".nav");
  const onScroll = () => bar.classList.toggle("scrolled", scrollY > 8);
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();
  const links = $$(".links a");
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        links.forEach((a) => a.classList.toggle("on", a.getAttribute("href") === `#${e.target.id}`));
      }
    }, { rootMargin: "-45% 0px -50% 0px" });
    links.forEach((a) => { const sec = $(a.getAttribute("href")); if (sec) io.observe(sec); });
  }
  const btn = $("[data-menu]"), sheet = $(".sheet");
  btn.addEventListener("click", () => {
    const open = sheet.hidden;
    sheet.hidden = !open;
    btn.setAttribute("aria-expanded", String(open));
  });
  sheet.addEventListener("click", (e) => { if (e.target.closest("a")) { sheet.hidden = true; btn.setAttribute("aria-expanded", "false"); } });
})();

// ---- reveal on scroll and counting numbers ------------------------------------------------------

(function reveal() {
  const els = $$(".reveal");
  if (REDUCE || !("IntersectionObserver" in window)) { els.forEach((el) => el.classList.add("in")); return; }
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
  }, { threshold: 0.08, rootMargin: "0px 0px -40px 0px" });
  els.forEach((el) => io.observe(el));
})();

function countUp(el) {
  const target = Number(el.dataset.count), pre = el.dataset.prefix || "", suf = el.dataset.suffix || "";
  const show = (v) => { el.textContent = pre + (el.dataset.sep ? fmt(v) : String(Math.round(v))) + suf; };
  if (REDUCE) return show(target);
  const t0 = performance.now(), dur = 1300;
  const step = (t) => {
    const k = Math.min(1, (t - t0) / dur);
    show(target * (1 - Math.pow(1 - k, 3)));
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
$$("[data-count]").forEach((el) => whenVisible(el, () => countUp(el), 0.5));

// ---- hero: a small, live version of the product per person ---------------------------------------

(function hero() {
  const scene = $("#scene"), foot = $("#scene-foot"), tabs = $$(".persona-tabs button");
  let run = 0, auto = true, visible = true;
  const order = ["maya", "leo", "sam", "ava"];

  const add = (html, cls = "") => {
    const d = document.createElement("div");
    d.className = cls;
    d.innerHTML = html;
    scene.append(d);
    requestAnimationFrame(() => d.classList.add("show"));
    return d;
  };
  async function type(el, text, id) {
    if (REDUCE) { el.textContent = text; return; }
    el.classList.add("caret");
    for (let i = 0; i < text.length; i += 2) {
      if (id !== run) return;
      el.textContent = text.slice(0, i + 2);
      await sleep(16);
    }
    el.classList.remove("caret");
  }
  const footer = (p, model, extra = "") => {
    foot.innerHTML = `<span>key <b>${esc(p.key)}</b></span><span>·</span><span>model <b>${esc(model)}</b></span><span>·</span>` +
      `<span>budget <b>$${p.spent.toFixed(2)}</b> of $${p.budget.toFixed(2)}</span>${extra}`;
  };

  const scenes = {
    async maya(id) {
      const p = PEOPLE.maya;
      footer(p, "gemini-flash");
      add("How is a candidate's overall score calculated?", "msg me");
      await sleep(700);
      const ai = add("", "msg ai");
      const t = document.createElement("span");
      ai.append(t);
      await type(t, "Each answer gets a rubric score, weighted by how important its question is, then averaged and clamped to 0–100 before it's shown.", id);
      if (id !== run) return;
      const c = document.createElement("div");
      c.innerHTML = `<span class="cite">${icon("check")}lib/score.mjs:12–30</span><span class="cite">${icon("check")}lib/rubric.mjs:4–18</span>`;
      ai.append(c);
      await sleep(500);
      add(`${icon("shield")}<span>2 of 2 citations checked against the lines the assistant read</span>`, "status-line");
      await sleep(400);
      add(`${icon("check")}<span>No writes at Ask level: a change request goes to Sam, the code owner</span>`, "status-line");
    },
    async leo(id) {
      const p = PEOPLE.leo;
      footer(p, "gemini-flash");
      add("Make the Begin interview button our brand orange.", "msg me");
      await sleep(700);
      const ai = add("", "msg ai");
      await type(ai, "That's in public/css/app.css, inside your allow-list. Here's the change:", id);
      if (id !== run) return;
      await sleep(300);
      add(`<div class="f"><span>public/css/app.css</span><span>line 42</span></div><div class="del">-  background: #2563eb;</div><div class="add">+  background: #ff6b35;</div>`, "diff msg show");
      await sleep(900);
      add(`${icon("pr")}<span>Pull request #42 opened under policy, in Leo's name</span>`, "status-line");
      await sleep(700);
      add(`${icon("check")}<span>CI allow-list check passed · waiting for Sam's review</span>`, "status-line");
    },
    async sam(id) {
      const p = PEOPLE.sam;
      footer(p, "qwen-coder");
      const term = add("", "term msg");
      const lines = [
        ["p", "$ cd ~/projects/firstround-demo && gemini"],
        ["d", "  Signed in through RoleSpace · key sam-build · qwen-coder"],
        ["p", "> add a unit test for the score clamp"],
        ["d", "  ✓ wrote test/score.test.mjs (+24 lines) · 3 tests pass"],
        ["w", "$ curl https://aiplatform.googleapis.com/…  → 403"],
        ["d", "  Only the gateway may call models: every call is counted"],
      ];
      for (const [cls, text] of lines) {
        if (id !== run) return;
        const ln = document.createElement("div");
        ln.className = cls;
        term.append(ln);
        await type(ln, text, id);
        await sleep(220);
      }
      add(REPOS.map((r) => `<div><b>${esc(r.id)}</b>cloned · VS Code · Gemini CLI</div>`).join(""), "mini-repos msg");
    },
    async ava(id) {
      const p = PEOPLE.ava;
      foot.innerHTML = `<span>audit chain <b>verified</b></span><span>·</span><span>1,284 events</span><span>·</span><span>head <b>9f3a1c…</b></span>`;
      add(`<div><span>Spend this month</span><b>$1.50</b></div><div><span>Model calls</span><b>513</b></div><div><span>Blocked</span><b>23</b></div>`, "mini-dash msg");
      await sleep(400);
      const rows = add(Object.entries(PEOPLE).map(([pid, x]) =>
        `<div class="mini-person" data-p="${pid}"><span class="av ${x.level}">${x.init}</span><span><b>${esc(x.first)}</b> · ${LEVEL[x.level]}</span>` +
        `<span class="meter"><i></i></span><button class="toggle" aria-label="${esc(x.first)}'s key on" tabindex="-1"></button></div>`).join(""), "mini-people msg");
      await sleep(200);
      $$(".mini-person", rows).forEach((r) => {
        const x = PEOPLE[r.dataset.p];
        $(".meter i", r).style.width = `${Math.max(3, (x.spent / x.budget) * 100)}%`;
      });
      await sleep(1600);
      if (id !== run) return;
      $('[data-p="leo"] .toggle', rows).classList.add("off");
      add(`${icon("x")}<span>Ava suspended Leo's key: his assistant, pull requests and workspace stop at once</span>`, "status-line bad");
      await sleep(1400);
      if (id !== run) return;
      $('[data-p="leo"] .toggle', rows).classList.remove("off");
      add(`${icon("check")}<span>Key restored. Both actions are in the hash-chained audit log</span>`, "status-line");
      void p;
    },
  };

  async function play(pid) {
    const id = ++run;
    tabs.forEach((b) => { const on = b.dataset.persona === pid; b.classList.toggle("on", on); b.setAttribute("aria-selected", String(on)); });
    scene.innerHTML = "";
    await scenes[pid](id);
    if (id !== run || !auto) return;
    await sleep(3200);
    while (!visible && id === run) await sleep(500);
    if (id === run && auto) play(order[(order.indexOf(pid) + 1) % order.length]);
  }
  tabs.forEach((b) => b.addEventListener("click", () => { auto = false; play(b.dataset.persona); }));
  if ("IntersectionObserver" in window) {
    new IntersectionObserver((e) => { visible = e[0].isIntersecting; }).observe($(".hero-card"));
  }
  play("maya");
})();

// ---- the connection graph: people -> policy -> models and repositories ---------------------------

(function graph() {
  const svg = $("#graph-svg"), tabs = $("#graph-tabs"), caption = $("#graph-caption");
  if (!svg) return;
  const NS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs = {}, parent = svg) => {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    parent.append(n);
    return n;
  };
  const W = 200, H = 50;
  const people = Object.keys(PEOPLE).map((pid, i) => ({ id: pid, x: 20, y: 70 + i * 104 }));
  const hub = { x: 470, y: 205, w: 180, h: 110 };
  const models = MODELS.filter((m) => m.on).map((m, i) => ({ id: m.id, x: 900, y: 40 + i * 64 }));
  const repos = REPOS.map((r, i) => ({ id: r.id, x: 900, y: 320 + i * 64 }));
  const controls = [["Budgets", "per key"], ["Usage", "per person"], ["Audit log", "hash-chained"]].map((c, i) => ({ c, x: 380 + i * 128, y: 430 }));

  el("text", { x: 20, y: 40, class: "col" }).textContent = "People";
  el("text", { x: 900, y: 24, class: "col" }).textContent = "Models";
  el("text", { x: 900, y: 304, class: "col" }).textContent = "Repositories";
  const curve = (x1, y1, x2, y2) => { const mx = (x1 + x2) / 2; return `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`; };
  const edges = [];
  const edge = (d, from, to) => {
    const path = el("path", { d, class: "edge" });
    const dot = el("circle", { r: 3.5, class: "pulse" });
    if (!REDUCE) {
      const anim = el("animateMotion", { dur: `${2.2 + Math.random() * 1.4}s`, repeatCount: "indefinite", path: d }, dot);
      void anim;
    }
    edges.push({ path, dot, from, to });
  };
  people.forEach((p) => edge(curve(p.x + W, p.y + H / 2, hub.x, hub.y + hub.h / 2), p.id, "hub"));
  models.forEach((m) => edge(curve(hub.x + hub.w, hub.y + 30, m.x, m.y + H / 2), "hub", m.id));
  repos.forEach((r) => edge(curve(hub.x + hub.w, hub.y + hub.h - 30, r.x, r.y + H / 2), "hub", r.id));
  controls.forEach((c, i) => edge(`M${hub.x + hub.w / 2},${hub.y + hub.h} L${c.x + 55},${c.y}`, "hub", `ctl${i}`));

  const nodes = {};
  const node = (id, x, y, w, h, title, sub, cls, pad = 16) => {
    const g = el("g", { class: `node ${cls}`, transform: `translate(${x},${y})`, "data-id": id });
    el("rect", { width: w, height: h, rx: 10 }, g);
    const t = el("text", { x: pad, y: sub ? 22 : h / 2 + 5, class: "t" }, g);
    t.textContent = title;
    if (sub) { const s = el("text", { x: pad, y: 38, class: "s" }, g); s.textContent = sub; }
    nodes[id] = g;
    return g;
  };
  people.forEach((p) => {
    const x = PEOPLE[p.id];
    const g = node(p.id, p.x, p.y, W, H, `${x.first} · ${x.title}`, `${LEVEL[x.level]} level · ${usd(x.budget)}/month`, "person", 28);
    el("circle", { cx: 15, cy: 17, r: 5, class: `lv ${x.level}` }, g);
    g.setAttribute("tabindex", "0");
    g.setAttribute("role", "button");
    g.addEventListener("click", () => select(p.id));
    g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(p.id); } });
  });
  const hg = el("g", { class: "node hub", transform: `translate(${hub.x},${hub.y})` });
  el("rect", { width: hub.w, height: hub.h, rx: 14 }, hg);
  [["RoleSpace policy", 44, "t"], ["role.yaml · one version", 66, "s"], ["checks every call", 86, "s"]].forEach(([s, y, c]) => {
    const t = el("text", { x: hub.w / 2, y, class: c, "text-anchor": "middle" }, hg); t.textContent = s;
  });
  models.forEach((m) => {
    const mm = MODELS.find((x) => x.id === m.id);
    const g = node(m.id, m.x, m.y, W, H, modelLabel(m.id), mm.provider + " · Vertex AI", "model", 44);
    el("image", { href: `/assets/logos/${mm.logo}.svg`, x: 14, y: 14, width: 22, height: 22 }, g);
  });
  repos.forEach((r) => node(r.id, r.x, r.y, W, H, r.id, REPOS.find((x) => x.id === r.id).name, "repo"));
  controls.forEach((c, i) => node(`ctl${i}`, c.x, c.y, 110, H, c.c[0], c.c[1], "ctl"));

  function select(pid) {
    $$("button", tabs).forEach((b) => b.classList.toggle("on", b.dataset.p === pid));
    const ms = new Set(keyModels(pid)), rs = ACCESS[pid];
    const reach = new Set([pid, "hub", "ctl0", "ctl1", "ctl2", ...ms, ...rs]);
    Object.entries(nodes).forEach(([id, g]) => {
      g.classList.toggle("hot", reach.has(id) && id !== "hub");
      g.classList.toggle("cold", !reach.has(id));
    });
    edges.forEach((e) => {
      const hot = (e.from === pid) || (e.from === "hub" && reach.has(e.to));
      e.path.classList.toggle("hot", hot); e.path.classList.toggle("cold", !hot);
      e.dot.classList.toggle("hot", hot);
    });
    const p = PEOPLE[pid];
    caption.innerHTML = `<b>${esc(p.first)}</b>, ${esc(p.title.toLowerCase())} (${LEVEL[p.level]}): ${[...ms].map(modelLabel).join(", ")} · ` +
      `${rs.size} of ${REPOS.length} repositories · ${usd(p.budget)}/month on key <code>${esc(p.key)}</code>. Everything greyed out is unreachable for ${esc(p.first)}.`;
  }
  tabs.innerHTML = Object.entries(PEOPLE).map(([pid, x]) => `<button role="tab" data-p="${pid}"><span class="dot ${x.level}"></span>${esc(x.first)} · ${LEVEL[x.level]}</button>`).join("");
  $$("button", tabs).forEach((b) => b.addEventListener("click", () => select(b.dataset.p)));
  select("leo");
})();

// ---- policy simulator --------------------------------------------------------------------------

(function simulator() {
  const ACTIONS = [
    { id: "ask", label: "Ask how scoring works", icon: "chat", tag: "question" },
    { id: "css", label: "Change the button colour", icon: "code", tag: "public/css/app.css" },
    { id: "logic", label: "Change the scoring logic", icon: "code", tag: "lib/score.mjs" },
    { id: "pro", label: "Use Gemini 3.1 Pro", icon: "spark", tag: "gemini-pro" },
    { id: "ws", label: "Open a coding workspace", icon: "terminal", tag: "workspace" },
    { id: "budget", label: "Raise a teammate's budget", icon: "gauge", tag: "admin" },
  ];
  const state = { p: "leo", a: "logic" };
  let run = 0;
  const peopleEl = $("#sim-people"), actionsEl = $("#sim-actions"), checks = $("#sim-checks"), verdict = $("#sim-verdict");

  peopleEl.innerHTML = Object.entries(PEOPLE).map(([pid, x]) =>
    `<button class="person" data-p="${pid}"><span class="av ${x.level}">${x.init}</span><span><b>${esc(x.name)}</b><small>${esc(x.title)} · ${LEVEL[x.level]}</small></span></button>`).join("");
  actionsEl.innerHTML = ACTIONS.map((a) => `<button class="action" data-a="${a.id}">${icon(a.icon)}<span>${esc(a.label)}</span><code>${esc(a.tag)}</code></button>`).join("");

  /** The same order of checks as production: identity, level, tool, scope, budget. */
  function decide(pid, aid) {
    const p = PEOPLE[pid], lvl = p.level, L = LEVEL[lvl], email = `${pid}@firstround.example`;
    const steps = [
      { t: "Identity", d: `Signed in with Google as ${email} (Identity-Aware Proxy)`, ok: true },
      { t: "Level", d: `${L}, from ${p.first}'s team in role.yaml`, ok: true },
    ];
    const budget = { t: "Budget", d: `$${p.spent.toFixed(2)} of $${p.budget.toFixed(2)} used this month on key ${p.key}`, ok: true };
    const toOwner = "RoleSpace drafts a request to Sam, who owns the screening code, with the person's own words.";
    let out;
    if (aid === "ask") {
      steps.push({ t: "Tool", d: `Reading and searching code is allowed at ${L}`, ok: true },
                 { t: "Repository", d: `firstround-demo is on ${p.first}'s list`, ok: true }, budget);
      out = { ok: true, title: "Allowed", why: "Every level can ask questions about its repositories.",
              next: "The answer cites exact lines, and code checks each citation against what the assistant read. About 1¢." };
    } else if (aid === "css" || aid === "logic") {
      const path = aid === "css" ? "public/css/app.css" : "lib/score.mjs";
      if (lvl === "suggest") {
        const inList = aid === "css";
        steps.push({ t: "Tool", d: "propose_edit is allowed at Suggest", ok: true },
                   { t: "Path", d: inList ? `${path} matches public/css/** on the allow-list` : `${path} is not on the allow-list (public/css/**, public/**/*.html)`, ok: inList });
        if (inList) steps.push(budget);
        out = inList
          ? { ok: true, title: "Allowed, as a pull request", why: "Rule: levels.suggest.allow_paths in role.yaml.", next: "Diff preview, then a pull request in Leo's name, a CI allow-list check and one human review." }
          : { ok: false, title: "Blocked: outside Leo's allow-list", why: "Rule: levels.suggest.allow_paths. Anything not allowed is denied, and the check runs again when the pull request opens.", next: toOwner };
      } else if (lvl === "build") {
        steps.push({ t: "Tool", d: "Build edits in a private workspace, not through the assistant", ok: true },
                   { t: "Repository", d: "firstround-demo is cloned in Sam's workspace", ok: true }, budget);
        out = { ok: true, title: "Allowed, in Sam's workspace", why: "Build level gets a private Coder workspace with its repositories.", next: "Sam pushes with his own GitHub access; branch protection still needs a review." };
      } else {
        steps.push({ t: "Tool", d: `${L} level has no edit tool`, ok: false });
        out = { ok: false, title: `Not at ${L} level`, why: `Rule: levels.${lvl}.tools in role.yaml has no propose_edit, so the tool isn't even offered.`,
                next: lvl === "ask" ? `${toOwner} Maya can also ask for Suggest for up to 8 hours.` : toOwner };
      }
    } else if (aid === "pro") {
      const has = LEVEL_MODELS[lvl].has("gemini-pro");
      steps.push({ t: "Tool", d: "Choosing a model is allowed at every level", ok: true },
                 { t: "Model", d: has ? `gemini-pro is on key ${p.key}` : `gemini-pro isn't on key ${p.key} (${[...LEVEL_MODELS[lvl]].join(", ")})`, ok: has });
      if (has) steps.push(budget);
      out = has ? { ok: true, title: "Allowed", why: `Rule: levels.${lvl}.models includes gemini-pro.`, next: "The call is tagged with person, project and model for the usage report." }
                : { ok: false, title: "The gateway refuses the call", why: `Rule: levels.${lvl}.models, enforced by the gateway on ${p.first}'s own key.`, next: "Even a direct call with this key is refused. An admin can add the model in Govern → Policy." };
    } else if (aid === "ws") {
      const ok = lvl === "build";
      steps.push({ t: "Workspace", d: ok ? "A private Coder workspace comes with Build level" : `Workspaces are Build level only; ${p.first} is ${L}`, ok });
      if (ok) steps.push({ t: "Repositories", d: "Clones firstround-demo, RoleSpace and firstround: only Sam's", ok: true }, budget);
      out = ok ? { ok: true, title: "Allowed", why: "Rule: levels.build.", next: "Opens through an Identity-Aware Proxy tunnel. No VPN, no public IP." }
               : { ok: false, title: "Not at this level", why: "Rule: only levels.build gets a workspace.", next: "An admin can change the level in Govern → People, and the change is logged." };
    } else {
      const ok = lvl === "govern";
      steps.push({ t: "Admin", d: ok ? "Govern level may change budgets" : `Admin actions are Govern level only; ${p.first} is ${L}`, ok });
      if (ok) steps.push({ t: "Confirmation", d: "Admin change confirmed", ok: true });
      out = ok ? { ok: true, title: "Allowed", why: "Rule: Govern level.", next: "The new budget is applied to the key at once and written to the hash-chained audit log." }
               : { ok: false, title: "Not allowed", why: "Rule: only Govern level can change budgets.", next: "The person can request more budget; an admin approves it." };
    }
    return { steps, out };
  }

  async function check() {
    const id = ++run;
    $$(".person", peopleEl).forEach((b) => b.classList.toggle("on", b.dataset.p === state.p));
    $$(".action", actionsEl).forEach((b) => b.classList.toggle("on", b.dataset.a === state.a));
    const { steps, out } = decide(state.p, state.a);
    const all = [...steps];
    const failAt = all.findIndex((s) => !s.ok);
    const names = ["Identity", "Level", "Tool", "Scope", "Budget"];
    while (failAt >= 0 && all.length < 5) all.push({ t: names[all.length], d: "Not checked: an earlier check decided", skip: true });
    checks.innerHTML = all.map((s) => `<li><span class="st"></span><div><b>${esc(s.t)}</b><span>${esc(s.d)}</span></div></li>`).join("");
    verdict.className = "verdict";
    const lis = $$("li", checks);
    for (let i = 0; i < all.length; i++) {
      if (id !== run) return;
      const li = lis[i], s = all[i];
      if (s.skip || (failAt >= 0 && i > failAt)) {
        li.classList.add("done", "skipped");
        $(".st", li).innerHTML = icon("arrow");
        $("span:last-child", li).textContent = "Not checked: an earlier check decided";
        continue;
      }
      li.classList.add("run");
      await sleep(420);
      if (id !== run) return;
      li.classList.remove("run");
      li.classList.add("done", s.ok ? "pass" : "fail");
      $(".st", li).innerHTML = icon(s.ok ? "check" : "x");
    }
    verdict.innerHTML = `<h4>${icon(out.ok ? "check" : "x")}${esc(out.title)}</h4><p>${esc(out.why)}</p><div class="next">${esc(out.next)}</div>`;
    verdict.classList.add("show", out.ok ? "ok" : "no");
  }
  // Live loop: walk through the interesting cases on its own. A click takes over; after a quiet
  // spell the loop picks up again, so the section never sits still.
  const DEMO = [["maya", "ask"], ["maya", "css"], ["leo", "css"], ["leo", "logic"], ["maya", "pro"], ["leo", "pro"],
                ["sam", "ws"], ["leo", "ws"], ["ava", "budget"], ["sam", "budget"], ["sam", "logic"]];
  const HOLD = 3200, RESUME = 15000;
  const playBtn = $("#sim-play"), bar = $("#sim-bar"), cap = $("#sim-caption");
  let auto = !REDUCE, visible = false, idx = 0, lastTouch = 0;
  const setAuto = (on) => {
    auto = on;
    playBtn.setAttribute("aria-pressed", String(on));
    playBtn.innerHTML = `${icon(on ? "pause" : "play")}<span>${on ? "Pause" : "Play"}</span>`;
    cap.textContent = on ? "Running on its own. Click any person or action to try it yourself." : "Paused. Your choice stays on screen.";
    if (!on) { bar.style.transition = "none"; bar.style.width = "0"; }
  };
  const hold = async () => {   // the verdict stays up while the bar fills
    bar.style.transition = "none"; bar.style.width = "0";
    void bar.offsetWidth;
    bar.style.transition = `width ${HOLD}ms linear`; bar.style.width = "100%";
    await sleep(HOLD);
  };
  async function loop() {
    for (;;) {
      if (!auto && lastTouch && Date.now() - lastTouch > RESUME && playBtn.dataset.stopped !== "1") setAuto(true);
      if (auto && visible && !document.hidden) {
        [state.p, state.a] = DEMO[idx++ % DEMO.length];
        const mine = run + 1;
        await check();
        if (auto && run === mine) await hold();
      } else {
        await sleep(400);
      }
    }
  }
  const takeOver = () => { lastTouch = Date.now(); setAuto(false); };
  peopleEl.addEventListener("click", (e) => { const b = e.target.closest(".person"); if (b) { takeOver(); state.p = b.dataset.p; check(); } });
  actionsEl.addEventListener("click", (e) => { const b = e.target.closest(".action"); if (b) { takeOver(); state.a = b.dataset.a; check(); } });
  playBtn.addEventListener("click", () => {
    const on = !auto;
    playBtn.dataset.stopped = on ? "" : "1";   // a deliberate pause isn't undone by the idle timer
    lastTouch = Date.now();
    setAuto(on);
  });
  if ("IntersectionObserver" in window) {
    new IntersectionObserver((e) => { visible = e[0].isIntersecting; }, { threshold: 0.25 }).observe($("#try .sim"));
  } else visible = true;
  setAuto(auto);
  if (REDUCE) whenVisible($("#try .sim"), check, 0.3); else loop();
})();

// ---- models by level, and what each key allows ---------------------------------------------------

(function models() {
  const table = $("#model-matrix"), preview = $("#key-preview");
  const levels = Object.keys(LEVEL);
  function render() {
    table.innerHTML = `<thead><tr><th>Model</th><th>Switched on</th>${levels.map((l) => `<th><span class="chip ${l}">${LEVEL[l]}</span></th>`).join("")}</tr></thead><tbody>` +
      MODELS.map((m) => `<tr class="${m.on ? "" : "off"}"><td><div class="mrow">${logo(m.id, 24)}<span><b>${esc(m.label)}</b><small>${esc(m.provider)} · Vertex AI</small></span></div></td>` +
        `<td><button class="toggle ${m.on ? "" : "off"}" data-model="${m.id}" aria-label="${esc(m.label)} switched ${m.on ? "on" : "off"}"></button></td>` +
        levels.map((l) => { const on = m.on && LEVEL_MODELS[l].has(m.id);
          return `<td><button class="cell ${on ? "on" : ""}" data-m="${m.id}" data-l="${l}" ${m.on ? "" : "disabled"} aria-pressed="${on}" aria-label="${esc(m.label)} for ${LEVEL[l]}">${icon("check")}</button></td>`; }).join("") +
        "</tr>").join("") + "</tbody>";
    preview.innerHTML = Object.entries(PEOPLE).map(([pid, x]) => {
      const ms = keyModels(pid);
      return `<div class="key-row"><span class="av ${x.level}">${x.init}</span><div><b>${esc(x.first)}</b><code>${esc(x.key)}</code><div class="tags">` +
        (ms.length ? ms.map((m) => `<span class="tag">${logo(m, 13)}${esc(modelLabel(m))}</span>`).join("") : `<span class="tag none">No models: every call is refused</span>`) + "</div></div></div>";
    }).join("");
  }
  table.addEventListener("click", (e) => {
    const cell = e.target.closest(".cell"), tog = e.target.closest(".toggle");
    if (cell && !cell.disabled) {
      const set = LEVEL_MODELS[cell.dataset.l];
      set.has(cell.dataset.m) ? set.delete(cell.dataset.m) : set.add(cell.dataset.m);
      render();
      $(`.cell[data-m="${cell.dataset.m}"][data-l="${cell.dataset.l}"]`, table)?.classList.add("flash");
    } else if (tog) {
      const m = MODELS.find((x) => x.id === tog.dataset.model);
      m.on = !m.on;
      if (m.on && ![...Object.values(LEVEL_MODELS)].some((s) => s.has(m.id))) { LEVEL_MODELS.suggest.add(m.id); LEVEL_MODELS.build.add(m.id); }
      render();
    }
  });
  render();
})();

(function accessTabs() {
  const tabs = $$("#access-tabs button");
  tabs.forEach((b) => b.addEventListener("click", () => {
    tabs.forEach((x) => { const on = x === b; x.classList.toggle("on", on); x.setAttribute("aria-selected", String(on)); $(`#${x.dataset.panel}`).hidden = !on; });
  }));
})();

// ---- repository access with a hash-chained audit log ---------------------------------------------

(function repos() {
  const table = $("#repo-matrix"), audit = $("#audit");
  let head = "0".repeat(64);
  async function sha(text) {
    if (crypto.subtle) {
      const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
      return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
    }
    let h = 0x811c9dc5;   // FNV-1a fallback outside secure contexts
    for (const ch of text) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619) >>> 0; }
    return h.toString(16).padStart(8, "0").repeat(8);
  }
  async function log(who, text, fresh = true) {
    const prev = head;
    head = await sha(JSON.stringify({ who, text, prev }));
    const li = document.createElement("li");
    li.innerHTML = `<b>${esc(who)}</b> ${esc(text)}<div class="h"><span>hash <i>${head.slice(0, 10)}…</i></span><span>prev ${prev.slice(0, 10)}…</span></div>`;
    if (fresh) { audit.querySelector(".new")?.classList.remove("new"); li.classList.add("new"); }
    audit.prepend(li);
  }
  function render() {
    table.innerHTML = `<thead><tr><th>Person</th>${REPOS.map((r) => `<th>${esc(r.name)}<small>${esc(r.id)}</small></th>`).join("")}</tr></thead><tbody>` +
      Object.entries(PEOPLE).map(([pid, x]) => `<tr><td><span class="av ${x.level}">${x.init}</span><span><b>${esc(x.first)}</b><small>${LEVEL[x.level]}</small></span></td>` +
        REPOS.map((r) => { const on = ACCESS[pid].has(r.id);
          return `<td><button class="cell ${on ? "on" : ""}" data-p="${pid}" data-r="${r.id}" aria-pressed="${on}" aria-label="${esc(x.first)} access to ${esc(r.id)}">${icon("check")}</button></td>`; }).join("") +
        "</tr>").join("") + "</tbody>";
  }
  table.addEventListener("click", async (e) => {
    const cell = e.target.closest(".cell");
    if (!cell) return;
    const { p, r } = cell.dataset, set = ACCESS[p], x = PEOPLE[p];
    const gave = !set.has(r);
    gave ? set.add(r) : set.delete(r);
    render();
    $(`.cell[data-p="${p}"][data-r="${r}"]`, table)?.classList.add("flash");
    const ws = x.level === "build" ? ` · ${x.first}'s workspace clones ${set.size} ${set.size === 1 ? "repository" : "repositories"} at its next start` : "";
    await log("Ava Rossi", `${gave ? "gave" : "removed"} ${x.first}'s access to ${r}${ws}`);
  });
  render();
  (async () => {
    await log("Ava Rossi", "added Nina Patel at Ask level, by work email", false);
    await log("Ava Rossi", "switched on Qwen3 Coder for Suggest and Build", false);
    await log("Leo Park", "opened pull request #42 in public/css/app.css", false);
  })();
})();

// ---- collaboration flow: from a sentence to a merged pull request ------------------------------

(function flow() {
  const steps = $$("#flow-steps li"), stage = $("#flow-stage"), btn = $("#flow-play"), cap = $("#flow-caption");
  const STEPS = [
    { h: "Leo asks in plain words", p: "No ticket, no waiting for a developer. The assistant finds the right file and checks Leo's allow-list before it writes anything.",
      ui: `<div class="msg me show">Make the Begin interview button our brand orange, #FF6B35.</div><div class="msg ai show">That's in public/css/app.css, inside your allow-list. Here's the change.</div>` },
    { h: "He reviews the exact change", p: "A diff shows exactly what changes. Nothing reaches GitHub until Leo chooses to open a pull request.",
      ui: `<div class="diff"><div class="f"><span>public/css/app.css</span><span>1 line</span></div><div class="del">-  background: #2563eb;</div><div class="add">+  background: #ff6b35;</div></div><div class="cta-row"><span class="btn primary">${icon("pr")}Open pull request</span><span class="btn secondary">Discard</span></div>` },
    { h: "A pull request in his name", p: "RoleSpace opens the pull request under policy, in Leo's name: he reviewed the change, so the credit is his. CI and a human review decide what merges.",
      ui: `<div class="pr"><div class="t">${icon("pr")}Make the Begin interview button brand orange <span class="state open">Open</span></div><div class="meta">#42 · rolespace/suggest-leo → main</div><div class="commit"><b>Leo Park</b> &lt;leo@firstround.example&gt; authored and committed</div></div>` },
    { h: "Checked, then reviewed", p: "CI checks the allow-list again and branch protection needs one human review. Code owners review in GitHub as they always do.",
      ui: `<div class="pr"><div class="t">${icon("pr")}#42 Make the Begin interview button brand orange</div><div class="row ok">${icon("check")}designer-allowlist check passed</div><div class="row ok">${icon("check")}Sam Okafor approved these changes</div><div class="row wait">${icon("gauge")}1 of 1 required review</div></div>` },
    { h: "Merged, and on the record", p: "Leo follows checks, review and comments on his Changes page. The audit log records who asked, when, and under which policy version.",
      ui: `<div class="pr"><div class="t">${icon("pr")}#42 Make the Begin interview button brand orange <span class="state merged">Merged</span></div><div class="row ok">${icon("check")}Checks passed · approved by Sam</div><div class="row ok">${icon("chain")}Audit: pr_opened by Leo · policy 7f1350e</div></div>` },
  ];
  const DUR = 4800;
  let cur = 0, playing = !REDUCE, timer = null;
  function show(i) {
    cur = i;
    steps.forEach((li, k) => {
      li.classList.toggle("on", k === i); li.classList.toggle("done", k < i); li.classList.remove("playing");
    });
    if (playing) { void steps[i].offsetWidth; steps[i].style.setProperty("--dur", `${DUR}ms`); steps[i].classList.add("playing"); }
    const s = STEPS[i];
    stage.innerHTML = `<div class="copy"><span class="eyebrow">Step ${i + 1} of 5</span><h3>${esc(s.h)}</h3><p>${esc(s.p)}</p></div><div class="ui">${s.ui}</div>`;
    cap.textContent = playing ? "Playing. Click a step to stop on it." : "Paused.";
    clearTimeout(timer);
    if (playing) timer = setTimeout(() => show((cur + 1) % STEPS.length), DUR);
  }
  function setPlaying(on) {
    playing = on;
    btn.innerHTML = `${icon(on ? "pause" : "play")}<span>${on ? "Pause" : "Play"}</span>`;
    show(cur);
  }
  steps.forEach((li, i) => li.addEventListener("click", () => { playing = false; setPlaying(false); show(i); }));
  btn.addEventListener("click", () => setPlaying(!playing));
  show(0);
  clearTimeout(timer);
  whenVisible($("#flow-stage"), () => setPlaying(!REDUCE), 0.4);
})();

// ---- usage dashboard (simulated, clearly labelled) ------------------------------------------------

(function usage() {
  const bars = $("#bars"), budgets = $("#budgets");
  const N = 24, STEP = 2400;   // one bar per interval, newest on the right
  const series = Array.from({ length: N }, (_, i) => Math.round(26000 + 14000 * Math.sin(i / 3) ** 2 + (i % 4) * 3500));
  let stamp = Date.now() - (N - 1) * 60000;
  const stamps = Array.from({ length: N }, (_, i) => stamp + i * 60000);
  const hhmm = (t) => new Date(t).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
  bars.insertAdjacentHTML("afterend", `<div class="bars-axis"><span id="ax-from"></span><span>Tokens per minute, all models</span><span>now</span></div>`);
  const tip = document.createElement("div");
  tip.className = "tip"; tip.hidden = true;
  function draw() {
    const max = Math.max(...series) * 1.15;
    bars.innerHTML = series.map((t, i) => `<div data-i="${i}" class="${i === N - 1 ? "now" : ""}"><i></i></div>`).join("");
    bars.append(tip);
    $$("div[data-i]", bars).forEach((d, i) => { d.style.height = `${(series[i] / max) * 100}%`; });
    $("#ax-from").textContent = hhmm(stamps[0]);
  }
  bars.addEventListener("mousemove", (e) => {
    const b = e.target.closest("[data-i]");
    if (!b) { tip.hidden = true; return; }
    const i = Number(b.dataset.i), r = b.getBoundingClientRect(), host = bars.getBoundingClientRect();
    tip.innerHTML = `<b>${fmt(series[i])}</b> <span>tokens · ${hhmm(stamps[i])}</span>`;
    tip.style.left = `${r.left - host.left + r.width / 2}px`;
    tip.style.top = `${r.top - host.top - 6}px`;
    tip.hidden = false;
  });
  bars.addEventListener("mouseleave", () => { tip.hidden = true; });

  const spend = Object.fromEntries(Object.entries(PEOPLE).map(([pid, x]) => [pid, x.spent]));
  const renderBudgets = () => {
    budgets.innerHTML = Object.entries(PEOPLE).map(([pid, x]) => {
      const pct = (spend[pid] / x.budget) * 100;
      return `<tr><td><span class="av ${x.level}">${x.init}</span>${esc(x.first)}</td><td><span class="meter ${pct > 90 ? "bad" : pct > 70 ? "warn" : ""}"><i data-w="${Math.max(2, pct)}"></i></span></td>` +
        `<td>$${spend[pid].toFixed(2)} / $${x.budget.toFixed(2)}</td></tr>`;
    }).join("");
    requestAnimationFrame(() => $$(".meter i", budgets).forEach((i) => { i.style.width = `${i.dataset.w}%`; }));
  };
  const k = { in: 1.9e6, out: 62400, cost: 1.5, blocked: 23 };
  const kpis = () => {
    $("#k-in").textContent = compact(k.in); $("#k-out").textContent = compact(k.out);
    $("#k-cost").textContent = `$${k.cost.toFixed(2)}`; $("#k-blocked").textContent = fmt(k.blocked);
  };
  let current = 0;
  whenVisible($("#usage .dash"), () => {
    draw(); renderBudgets(); kpis();
    if (REDUCE) return;
    let ticks = 0;
    setInterval(() => {
      if (document.hidden) return;
      const pid = Object.keys(PEOPLE)[Math.floor(Math.random() * 3)];
      const tin = 6000 + Math.random() * 9000, tout = 150 + Math.random() * 400, c = tin * 0.0000006 + tout * 0.0000035;
      k.in += tin; k.out += tout; k.cost += c; spend[pid] += c;
      if (Math.random() < 0.1) k.blocked += 1;
      current += tin + tout;
      series[N - 1] = Math.max(series[N - 1], current);
      if (++ticks % 3 === 0) {   // a new interval: the chart scrolls left
        series.shift(); stamps.shift();
        series.push(Math.round(current * (0.9 + Math.random() * 0.4)));
        stamps.push(stamps[stamps.length - 1] + 60000);
        current = 0;
      }
      kpis(); renderBudgets(); draw();
    }, STEP);
  }, 0.3);
})();

// ---- ROI calculator ----------------------------------------------------------------------------

(function roi() {
  const box = $("#roi-inputs");
  if (!box) return;
  const F = [
    { id: "dev", label: "Developers", min: 5, max: 2000, step: 5, v: 100 },
    { id: "non", label: "PMs, designers and analysts", min: 0, max: 1000, step: 5, v: 40 },
    { id: "q", label: "Questions each asks a week", min: 1, max: 30, step: 1, v: 5 },
    { id: "ch", label: "Small changes each makes a month", min: 0, max: 20, step: 1, v: 2 },
    { id: "mq", label: "Developer minutes per question (assumption)", min: 5, max: 60, step: 5, v: 15, unit: " min" },
    { id: "mc", label: "Developer minutes per small change", min: 10, max: 120, step: 5, v: 45, unit: " min" },
    { id: "rate", label: "Loaded cost of a developer hour", min: 25, max: 250, step: 5, v: 75, pre: "$" },
  ];
  box.innerHTML = F.map((f) => `<label>${esc(f.label)} <output id="o-${f.id}"></output><input type="range" id="i-${f.id}" min="${f.min}" max="${f.max}" step="${f.step}" value="${f.v}"></label>`).join("");
  const INFRA = 1300;   // app, gateway, database and sign-in at list price, a year
  let lastValue = 0;
  function calc() {
    const v = Object.fromEntries(F.map((f) => [f.id, Number($(`#i-${f.id}`).value)]));
    F.forEach((f) => { $(`#o-${f.id}`).textContent = `${f.pre || ""}${fmt(v[f.id])}${f.unit || ""}`; });
    const questions = v.non * v.q * 48, changes = v.non * v.ch * 12;
    const hours = (questions * v.mq + changes * v.mc) / 60;
    const value = hours * v.rate;
    lastValue = value;
    const models = questions * 0.01 + changes * 0.03;
    const cost = INFRA + models;
    $("#r-hours").textContent = fmt(hours);
    const share = v.dev ? (hours / (v.dev * 1800)) * 100 : 0;
    $("#r-fte").textContent = `about ${(hours / 1800).toFixed(1)} developers' working years, ${share < 0.1 ? "<0.1" : share.toFixed(1)}% of your engineering time`;
    $("#r-value").textContent = money(value);
    $("#r-cost").textContent = money(cost);
    $("#r-cost-note").textContent = `${money(INFRA)} infrastructure + ${money(models)} model calls`;
    const mult = value / cost;
    $("#r-roi").textContent = `${mult >= 10 ? fmt(mult) : mult.toFixed(1)}×`;
    const days = cost / (value / 365);
    $("#r-payback").textContent = value > 0 ? `pays for itself in ${days < 1 ? "under a day" : `${Math.ceil(days)} day${Math.ceil(days) === 1 ? "" : "s"}`}` : "add people to see a return";
    const top = Math.max(value, cost, 1);
    $("#roi-vs").innerHTML =
      `<div class="vs-row"><b>Developer time</b><div class="track"><div class="fill" style-w="${(value / top) * 100}"></div></div><span class="amt">${money(value)}</span></div>` +
      `<div class="vs-row cost"><b>Running cost</b><div class="track"><div class="fill" style-w="${(cost / top) * 100}"></div></div><span class="amt">${money(cost)}</span></div>` +
      `<p class="vs-note">Per year. Developers' own speed-up with AI isn't counted, so this is the conservative case.</p>`;
    requestAnimationFrame(() => $$("#roi-vs .fill").forEach((f) => { f.style.width = `${f.getAttribute("style-w")}%`; }));
  }
  box.addEventListener("input", calc);
  calc();
  // Live: the yearly value spread over 48 working weeks of 40 hours, counted since the page opened.
  const opened = performance.now(), tickEl = $("#r-tick");
  const tick = () => {
    const perSecond = lastValue / (48 * 40 * 3600);
    tickEl.textContent = `$${(perSecond * (performance.now() - opened) / 1000).toFixed(2)}`;
  };
  if (!REDUCE) setInterval(tick, 200); else tick();
})();

// ---- integration steps ---------------------------------------------------------------------------

(function integrate() {
  const tabs = $$("#int-tabs button"), panel = $("#int-panel");
  const check = (t) => `<li>${icon("check")}<span>${t}</span></li>`;
  const avail = (now, next) => `<div class="avail">${now.map((x) => `<span class="now">${esc(x)}</span>`).join("")}${next.map((x) => `<span class="next">Next: ${esc(x)}</span>`).join("")}</div>`;
  const P = [
    { h: "Use the sign-in you already have.", li: ["People sign in with Google through Identity-Aware Proxy. No VPN, no new passwords.",
        "Each person's level comes from their team in one policy file.", "Directory groups from Entra ID or Okta map to levels, through SAML and SCIM."],
      now: ["Google sign-in", "Identity-Aware Proxy"], next: ["Entra ID", "Okta", "SCIM"],
      art: `<div class="flowline"><div>${icon("building")}Work email<em>maya@firstround.example</em></div><div class="arrow">↓ finds the organization</div>` +
           `<div>${icon("lock")}Google sign-in at the edge<em>Identity-Aware Proxy</em></div><div class="arrow">↓ team in the policy</div>` +
           `<div>${icon("users")}Level: <span class="chip ask">Ask</span><em>tools, models, budget follow</em></div></div>` },
    { h: "Connect the repositories you already use.", li: ["Add each repository as a project, with the team that owns it.",
        "Edits arrive as normal pull requests: your CI and branch protection still decide.", "Workspaces clone only the repositories a person may use."],
      now: ["GitHub", "GitHub Actions"], next: ["GitLab", "Bitbucket", "Azure DevOps"],
      art: `<div class="code"><span class="c"># role.yaml</span>\n<span class="k">projects</span>:\n  <span class="k">firstround</span>:\n    <span class="k">repo</span>: <span class="s">acme/screening-app</span>\n    <span class="k">team</span>: <span class="s">screening</span>\n    <span class="k">pull_requests</span>: <span class="n">true</span>\n  <span class="k">payments</span>:\n    <span class="k">repo</span>: <span class="s">acme/payments</span>\n    <span class="k">team</span>: <span class="s">platform</span></div>` },
    { h: "One readable policy, or a form.", li: ["role.yaml says who gets which level, tools, paths, models and budget.",
        "Admins can change models, budgets and limits in a form, and every key follows.", "A simulator explains any decision before you rely on it."],
      now: ["role.yaml", "Policy form", "Simulator"], next: ["Policy changes as pull requests"],
      art: `<div class="code"><span class="k">levels</span>:\n  <span class="k">ask</span>:      <span class="c"># PMs: answers with checked citations</span>\n    <span class="k">models</span>: [<span class="s">gemini-flash</span>, <span class="s">kimi-k2</span>]\n    <span class="k">budget_usd</span>: <span class="n">2.00</span>\n    <span class="k">rpm_limit</span>: <span class="n">30</span>\n  <span class="k">suggest</span>:  <span class="c"># designers: edits as pull requests</span>\n    <span class="k">allow_paths</span>: [<span class="s">"public/css/**"</span>, <span class="s">"public/**/*.html"</span>]\n    <span class="k">budget_usd</span>: <span class="n">2.50</span></div>` },
    { h: "Add a person by work email.", li: ["Pick their level, projects, models and budget in one form.",
        "RoleSpace creates their key, stores it in Secret Manager and logs it.", "Remove blocks the key at once: assistant, pull requests and workspace stop."],
      now: ["Onboarding by email", "Offboarding", "Temporary access"], next: ["Directory sync"],
      art: `<div class="form-mock"><div class="two"><div class="f">Work email<div class="v">nina@firstround.example</div></div><div class="f">Name<div class="v">Nina Patel</div></div></div>` +
           `<div class="two"><div class="f">Level<div class="v"><span class="chip ask">Ask</span></div></div><div class="f">Budget<div class="v">$2.00 a month</div></div></div>` +
           `<div class="plan"><div>${icon("check")}Key nina-ask: Gemini 3.8 Flash, Kimi K2</div><div>${icon("check")}Stored in Secret Manager</div><div>${icon("check")}Repositories: screening app</div></div>` +
           `<span class="btn primary">Create access</span></div>` },
    { h: "Know and cap what AI costs.", li: ["Usage by person, model, project and source, with a CSV export.",
        "Budgets and per-minute limits on every key, enforced by the gateway.", "A total cap for all AI, and a project-wide hard stop."],
      now: ["Usage page", "CSV export", "Budgets", "Rate limits"], next: ["BigQuery", "Budget alerts"],
      art: `<div class="flowline"><div>${icon("chat")}Every question or edit<em>tagged: person · project</em></div><div class="arrow">↓ the person's own key</div>` +
           `<div>${icon("key")}Model gateway<em>budget · rate limit · model list</em></div><div class="arrow">↓ only the gateway may call models</div>` +
           `<div>${icon("cloud")}Vertex AI in your project<em>tokens and cost logged</em></div></div>` },
  ];
  function show(i) {
    tabs.forEach((b, k) => { b.classList.toggle("on", k === i); b.setAttribute("aria-selected", String(k === i)); });
    const p = P[i];
    panel.innerHTML = `<div><h3>${esc(p.h)}</h3><ul>${p.li.map(check).join("")}</ul>${avail(p.now, p.next)}</div><div class="art">${p.art}</div>`;
  }
  tabs.forEach((b, i) => b.addEventListener("click", () => show(i)));
  show(0);
})();

// ---- log in to your organization -------------------------------------------------------------------

(function login() {
  const back = $("#login"), form = $("#login-form"), input = $("#login-email"), result = $("#login-result");
  let last = null, timer = null;
  const open = (e) => {
    last = e?.currentTarget || null;
    back.hidden = false;
    document.body.style.overflow = "hidden";
    result.innerHTML = "";
    input.classList.remove("err");
    setTimeout(() => input.focus(), 30);
  };
  const close = () => {
    back.hidden = true;
    document.body.style.overflow = "";
    clearTimeout(timer);
    last?.focus();
  };
  $$("[data-login]").forEach((b) => b.addEventListener("click", open));
  $$("[data-close]").forEach((b) => b.addEventListener("click", close));
  back.addEventListener("click", (e) => { if (e.target === back) close(); });
  document.addEventListener("keydown", (e) => {
    if (back.hidden) return;
    if (e.key === "Escape") close();
    if (e.key === "Tab") {   // keep focus inside the dialog
      const f = $$("button, input, a[href]", back).filter((x) => !x.disabled && x.offsetParent);
      const lastEl = f[f.length - 1];
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); lastEl.focus(); }
      else if (!e.shiftKey && document.activeElement === lastEl) { e.preventDefault(); f[0].focus(); }
    }
  });
  $$("[data-fill]").forEach((b) => b.addEventListener("click", () => { input.value = b.dataset.fill; input.focus(); }));

  const safeUrl = (u) => { try { const x = new URL(u); return x.protocol === "https:" ? x.href : null; } catch { return null; } };
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearTimeout(timer);
    const email = input.value.trim();
    if (email.length > 200 || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      input.classList.add("err");
      result.innerHTML = `<p class="error-text">Enter your full work email, like name@company.com.</p>`;
      return;
    }
    input.classList.remove("err");
    const btn = $("button[type=submit]", form);
    btn.disabled = true;
    $("span", btn).textContent = "Finding your organization…";
    try {
      const r = await fetch("/api/org", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) });
      const d = await r.json().catch(() => ({}));   // a proxy error page isn't JSON
      if (!r.ok) {
        throw new Error(typeof d.detail === "string" ? d.detail
          : r.status === 429 ? "Too many tries. Wait a minute, then try again." : "Can't reach RoleSpace right now. Try again in a moment.");
      }
      const url = safeUrl(d.workspace);
      if (!url) throw new Error("No workspace address");
      if (d.status === "found") {
        result.innerHTML = `<div class="found"><span class="org">${esc(d.org[0])}</span><div><b>${esc(d.org)}</b>Workspace found. Taking you to ${esc(d.sign_in)} sign-in…` +
          `<div class="go"><span class="bar"><i></i></span><a href="${esc(url)}">Go now</a></div></div></div>`;
        timer = setTimeout(() => location.assign(url), REDUCE ? 600 : 2300);
      } else {
        const why = d.status === "personal"
          ? "That's a personal account, so there's no company workspace to match."
          : `${esc(d.domain)} isn't on RoleSpace yet.`;
        result.innerHTML = `<div class="found"><span class="org">${esc(d.org[0])}</span><div><b>Try the ${esc(d.org)} demo workspace</b>${why} You can explore the made-up ${esc(d.org)} team instead: sign in with Google.` +
          `<div class="go"><a class="btn primary" href="${esc(url)}">Open the demo workspace</a></div><p class="fine">Access is invite-only during the pilot.</p></div></div>`;
      }
    } catch (err) {
      const known = err instanceof Error && !(err instanceof TypeError) && !(err instanceof SyntaxError);
      result.innerHTML = `<p class="error-text">${esc(known ? err.message : "Can't reach RoleSpace right now. Try again in a moment.")}</p>`;
    } finally {
      btn.disabled = false;
      $("span", btn).textContent = "Continue";
    }
  });
})();
