"""RoleSpace on Cloud Run: the Ask and Suggest agents, requests, and the Govern screens.

Sign-in is a persona switcher for the demo (IAP in front of the app is the production step).
Every model call goes through the rs-gateway with the person's own key.
"""

import asyncio
import collections
import csv
import datetime
import hmac
import io
import json
import logging
import pathlib
import re
import statistics
import threading
import time
import uuid
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from google.api_core import exceptions as gexc
from pydantic import BaseModel, Field

import access
import agents
import roles
import services

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)  # its INFO lines carry request URLs, some with keys
LOG = logging.getLogger("rolespace")
app = FastAPI(title="RoleSpace", docs_url=None, redoc_url=None)
STATIC = pathlib.Path(__file__).with_name("static")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
BUILD = str(int(time.time()))  # cache-buster for static files, new on every deploy
MAX_BUDGET_USD = 20.0
PR_LIMIT_PER_SESSION = 6   # pull requests per browser per hour
PR_LIMIT_TOTAL = 30        # and for everyone together
CHAT_LIMIT_PER_IP = 40     # per hour; the URL is public, budgets cap cost and these cap load
CHAT_LIMIT_TOTAL = 300
PASSCODE_SECRET = "demo-admin-passcode"
PASSCODE_NEEDED = "demo passcode required"
_pr_times: dict[str, list[float]] = collections.defaultdict(list)
_chat_times: dict[str, collections.deque] = collections.defaultdict(collections.deque)
_pr_inflight: set[str] = set()
_pr_lock = threading.Lock()
_chat_locks: dict[str, asyncio.Lock] = collections.defaultdict(asyncio.Lock)
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update({"Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff",
                             "Referrer-Policy": "same-origin", "X-Frame-Options": "DENY",
                             "Strict-Transport-Security": "max-age=31536000"})
    return response


@app.exception_handler(services.UpstreamError)
async def upstream_error(_req: Request, err: services.UpstreamError) -> JSONResponse:
    return JSONResponse({"detail": str(err)}, status_code=502)


def _ref() -> str:
    return uuid.uuid4().hex[:8]


@app.exception_handler(gexc.GoogleAPIError)
async def google_error(_req: Request, err: gexc.GoogleAPIError) -> JSONResponse:
    ref = _ref()
    LOG.exception("Google Cloud call failed (ref %s)", ref)
    return JSONResponse({"detail": f"A Google Cloud service didn't answer ({type(err).__name__}). Try again. "
                                   f"Reference {ref}.", "ref": ref}, status_code=503)


@app.exception_handler(Exception)
async def unexpected_error(_req: Request, err: Exception) -> JSONResponse:
    ref = _ref()
    LOG.exception("unexpected error (ref %s)", ref)
    return JSONResponse({"detail": f"Something went wrong on our side ({type(err).__name__}). It's logged as "
                                   f"reference {ref}.", "ref": ref}, status_code=500)


def _person(pid: str) -> dict:
    """The person as RoleSpace treats them now, including a temporary elevation."""
    try:
        return access.effective(pid)
    except KeyError:
        raise HTTPException(404, f"unknown person {pid}")


def _require_govern(pid: str) -> dict:
    p = _person(pid)
    if p["level"] != "govern":
        raise HTTPException(403, "Only the Govern level can open admin screens")
    return p


def _name(pid: str) -> str:
    try:
        return roles.person(pid)["name"]
    except KeyError:
        return pid


def _key_info(pid: str) -> dict:
    p = roles.person(pid)
    return services.key_info(f"{p['id']}-{p['base_level']}")  # aliases use the person's own level


def _convo(request: Request, pid: str) -> str:
    """Conversations are per browser and person: the browser sends a random id it keeps."""
    sid = request.headers.get("x-rs-session", "")
    return f"{sid if re.fullmatch(r'[A-Za-z0-9-]{8,64}', sid) else 'anon'}:{pid}"


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "?")


_pass = {"at": 0.0, "value": None}


def require_passcode(request: Request) -> None:
    """Admin writes and pull requests need the demo passcode, because the demo URL is public and
    the persona switcher stands in for sign-in. Off when the secret doesn't exist (local dev)."""
    if time.time() - _pass["at"] > 300:
        try:
            _pass["value"] = services.secret(PASSCODE_SECRET)
        except gexc.NotFound:
            _pass["value"] = None
        _pass["at"] = time.time()
    code = _pass["value"]
    if code and not hmac.compare_digest(request.headers.get("x-demo-passcode", "").encode(), code.encode()):
        raise HTTPException(401, PASSCODE_NEEDED)


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = (STATIC / "index.html").read_text().replace("__BUILD__", BUILD)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


@app.get("/health")  # Cloud Run reserves /healthz
def health() -> dict:
    return {"ok": True, "repo_commit": agents.REPO_SHA, "files": len(agents.repo_files()),
            "policy_version": roles.version()}


@app.get("/api/status")
def status() -> dict:
    """Service health for the status light in the top bar (cached for 20 s)."""
    return {**services.health(), "commit": agents.REPO_SHA, "policy_version": roles.version()}


def _viewer(request: Request) -> str | None:
    """The Google account IAP signed in, for display only (IAP sets this header on every request)."""
    email = request.headers.get("x-goog-authenticated-user-email", "")
    return email.split(":", 1)[-1] or None


@app.get("/api/people")
def people(request: Request) -> dict:
    cfg = roles.config()
    out = []
    for base in roles.people():
        p = access.effective(base["id"])
        lvl = p["level_cfg"]
        out.append({k: p[k] for k in ("id", "name", "title", "team", "level", "base_level", "grant", "email")} | {
            "models": lvl["models"], "budget_usd": lvl["budget_usd"], "tools": lvl["tools"],
            "allow_paths": lvl.get("allow_paths", []), "agent_model": lvl.get("agent_model", "gemini-flash"),
            "elevation_targets": roles.elevation_targets(p["base_level"])})
    levels = {k: {"models": v["models"], "budget_usd": v["budget_usd"], "tools": v["tools"],
                  "allow_paths": v.get("allow_paths", []), "deny_paths": v.get("deny_paths", [])}
              for k, v in cfg["levels"].items()}
    return {"company": cfg["company"], "repo": cfg["repo"], "commit": agents.REPO_SHA,
            "budget_period": cfg["budget_period"], "people": out, "levels": levels,
            "teams": cfg.get("teams", {}), "elevation": cfg.get("elevation", {}),
            "policy_version": roles.version(), "files": list(agents.repo_files()), "viewer": _viewer(request)}


@app.get("/api/me")
def me(person: str) -> dict:
    """The person's own key, as the gateway sees it: models, budget, spend, suspended or not."""
    p = _person(person)
    info = _key_info(p["id"])
    return {"models": info.get("models", []), "budget": info.get("max_budget"),
            "spent": info.get("spend", 0.0), "blocked": bool(info.get("blocked")),
            "budget_reset_at": info.get("budget_reset_at"), "level": p["level"], "grant": p["grant"]}


# --- Assistant ----------------------------------------------------------------------------

class ChatIn(BaseModel):
    person: str
    message: str = Field(max_length=8000)


def _rate_limit(ip: str) -> None:
    now = time.time()
    for q in (_chat_times[ip], _chat_times["*"]):
        while q and now - q[0] > 3600:
            q.popleft()
    if len(_chat_times[ip]) >= CHAT_LIMIT_PER_IP or len(_chat_times["*"]) >= CHAT_LIMIT_TOTAL:
        raise HTTPException(429, "Demo limit: too many questions this hour. Try again later.")
    _chat_times[ip].append(now)
    _chat_times["*"].append(now)


@app.post("/api/chat")
async def chat(body: ChatIn, request: Request) -> dict:
    if not body.message.strip():
        raise HTTPException(400, "empty message")
    try:
        roles.person(body.person)
    except KeyError:
        raise HTTPException(404, f"unknown person {body.person}")
    _rate_limit(_client_ip(request))
    key = _convo(request, body.person)
    async with _chat_locks[key]:  # one turn at a time per conversation: one ADK session each
        p = await run_in_threadpool(_person, body.person)
        result = await agents.chat(p, body.message.strip()[:4000], key)
    try:
        await run_in_threadpool(services.log_answer, {
            "person": p["id"], "level": p["level"], "model": result["model"], "seconds": result["seconds"],
            "citations": len(result["citations"]), "verified": sum(c["ok"] for c in result["citations"]),
            "refused": any(t["tool"] == "draft_request" for t in result["trace"]),
            "denied": any(t.get("flag") == "denied" for t in result["trace"]),
            "edits": len(result["edits"]), "blocked": (result["blocked"] or {}).get("kind"),
            "empty": result["empty"]})
    except Exception:
        LOG.exception("could not log the answer")  # the answer still goes back
    return result


class PersonIn(BaseModel):
    person: str


@app.post("/api/reset")
def reset(body: PersonIn, request: Request) -> dict:
    agents.reset(_convo(request, body.person))
    return {"ok": True}


class PrIn(BaseModel):
    person: str
    edit_id: str


@app.post("/api/open-pr", dependencies=[Depends(require_passcode)])
def open_pr(body: PrIn, request: Request) -> dict:
    p = _person(body.person)
    key = _convo(request, body.person)
    edit = agents.get_edit(key, body.edit_id)
    if not edit:
        raise HTTPException(404, "This preview has expired; ask for the edit again")
    # Checked again here, not only in the agent's tool: this is the call that writes.
    if "propose_edit" not in p["level_cfg"]["tools"] or not roles.path_allowed(p["level_cfg"], edit["path"]):
        services.audit("edit_denied", p["id"], p["level"], f"PR for {edit['path']} denied at open")
        raise HTTPException(403, f"{edit['path']} is outside the allow-list")
    with _pr_lock:
        if body.edit_id in _pr_inflight:
            raise HTTPException(409, "This pull request is already being opened")
        now, sid = time.time(), key.split(":")[0]
        for q in (_pr_times[sid], _pr_times["*"]):
            q[:] = [t for t in q if now - t < 3600]
        if len(_pr_times[sid]) >= PR_LIMIT_PER_SESSION or len(_pr_times["*"]) >= PR_LIMIT_TOTAL:
            raise HTTPException(429, "Demo limit: too many pull requests this hour")
        _pr_inflight.add(body.edit_id)
        _pr_times[sid].append(now)  # counted up front, so parallel requests can't pass the limit
        _pr_times["*"].append(now)
    try:
        # A fresh branch per attempt: a retry after a half-finished attempt doesn't hit "exists".
        branch = f"rolespace/suggest-{p['id']}-{edit['id']}-{int(time.time()) % 100000}"
        title = f"[RoleSpace] {edit['reason'][:70]}"
        body_md = (f"Proposed by **{p['name']}** ({p['title']}, {p['level'].title()} level) through RoleSpace.\n\n"
                   f"> {edit['reason']}\n\nOnly `{edit['path']}` changes. The `designer-allowlist` check and one "
                   f"human review are required before merge.\n\nPolicy version `{roles.version()}`.")
        url = services.open_pr(branch, edit["path"], edit["old_text"], edit["new_text"], title, body_md)
    finally:
        _pr_inflight.discard(body.edit_id)
    agents.drop_edit(key, body.edit_id)  # only once the PR exists; a failure keeps the preview
    try:
        services.audit("pr_opened", p["id"], p["level"], f"PR opened for {edit['path']}: {url}", url=url)
    except Exception:
        LOG.exception("PR opened but not audited: %s", url)  # the person still gets the link
    return {"url": url}


class EditIn(BaseModel):
    person: str
    edit_id: str


@app.post("/api/discard-edit")
def discard_edit(body: EditIn, request: Request) -> dict:
    agents.drop_edit(_convo(request, body.person), body.edit_id)
    return {"ok": True}


# --- Requests: refusals become tracked handoffs, access requests wait for approval ------

def _with_owner(r: dict) -> dict:
    # Requests drafted before teams had owners go to the team's owner from role.yaml.
    return {**r, "owner": r.get("owner") or roles.team_owner(r.get("team") or "")}


def _actions(r: dict, viewer: dict) -> list[str]:
    vid, gov = viewer["id"], viewer["level"] == "govern"
    owner = r.get("owner") == vid or gov
    mine = r.get("from") == vid
    st = r["status"]
    if r["type"] == "access":
        if st == "pending":
            return (["approve", "deny"] if gov else []) + (["cancel"] if mine else [])
        if st == "approved" and gov:
            return ["revoke"]
        return []
    if st == "open":
        return (["accept", "decline"] if owner else []) + (["cancel"] if mine else [])
    if st == "in_progress" and owner:
        return ["done", "decline"]
    return []


def _visible_requests(viewer: dict) -> list[dict]:
    rows = [_with_owner(r) for r in services.list_requests()]
    if viewer["level"] != "govern":
        rows = [r for r in rows if viewer["id"] in (r.get("from"), r.get("owner"))]
    for r in rows:
        r["from_name"], r["owner_name"] = _name(r.get("from", "")), _name(r.get("owner") or "")
        r["actions"] = _actions(r, viewer)
    return rows


@app.get("/api/requests")
def requests_list(person: str) -> dict:
    return {"requests": _visible_requests(_person(person))}


class AccessIn(BaseModel):
    person: str
    level: str
    hours: float = Field(gt=0, le=24, allow_inf_nan=False)
    reason: str = Field(min_length=3, max_length=300)


@app.post("/api/requests/access")
def request_access(body: AccessIn) -> dict:
    p = _person(body.person)
    if body.level not in roles.elevation_targets(p["base_level"]):
        raise HTTPException(403, f"role.yaml doesn't let the {p['base_level']} level ask for {body.level}")
    if p["grant"]:
        raise HTTPException(409, "You already have a temporary level")
    if any(r["type"] == "access" and r["status"] == "pending" and r.get("from") == p["id"]
           for r in services.list_requests()):
        raise HTTPException(409, "You already have an access request waiting for approval")
    hours = min(body.hours, roles.elevation_max_hours())
    approver = next((q["id"] for q in roles.people() if q["level"] == "govern"), None)
    rid = services.save_request(p["id"], "platform", f"Temporary {body.level.title()} access for {hours:g} h",
                                body.reason, kind="access", owner=approver, level=body.level, hours=hours)
    services.audit("access_requested", p["id"], p["level"],
                   f"{p['name']} asked for {body.level} for {hours:g} h: {body.reason}", request_id=rid)
    return {"id": rid}


class ActIn(BaseModel):
    person: str
    action: Literal["accept", "done", "decline", "cancel", "approve", "deny", "revoke"]
    note: str = Field(default="", max_length=300)


NEXT_STATUS = {"accept": "in_progress", "done": "done", "decline": "declined", "cancel": "cancelled",
               "approve": "approved", "deny": "denied", "revoke": "revoked"}


ADMIN_ACTIONS = {"approve", "deny", "revoke"}


@app.post("/api/requests/{rid}")
def request_act(rid: str, body: ActIn, request: Request) -> dict:
    if body.action in ADMIN_ACTIONS:
        require_passcode(request)
    viewer = _person(body.person)
    r = services.get_request(rid)
    if not r:
        raise HTTPException(404, "No such request")
    r = _with_owner(r)
    if body.action not in _actions(r, viewer):
        raise HTTPException(403, f"{viewer['name']} can't {body.action} this request now")
    extra = {}
    if body.action == "approve":
        try:
            g = access.grant(r["from"], r["level"], r.get("hours", 1), viewer["id"], r.get("details", ""), rid)
        except ValueError as e:
            raise HTTPException(409, str(e))
        extra = {"grant_id": g["id"], "expires_at": g["expires_at"]}
    elif body.action == "revoke":
        if not access.end(r["from"], viewer["id"], "revoked"):  # end() also marks the request
            services.update_request(rid, "revoked", viewer["id"], "grant had already ended")
        _invalidate()
        return {"ok": True}
    services.update_request(rid, NEXT_STATUS[body.action], viewer["id"], body.note, **extra)
    _invalidate()
    kind = "elevation_denied" if body.action == "deny" else "request_updated"
    if body.action != "approve":  # approve is logged by access.grant
        services.audit(kind, viewer["id"], viewer["level"],
                       f"{viewer['name']} set \"{r['title'][:80]}\" to {NEXT_STATUS[body.action].replace('_', ' ')}",
                       request_id=rid)
    return {"ok": True}


# --- Policy: explain any decision ----------------------------------------------------------

class ExplainIn(BaseModel):
    person: str
    target: str
    action: Literal["edit", "model", "tool", "workspace", "admin"]
    value: str = Field(default="", max_length=300)


@app.post("/api/policy/explain")
def policy_explain(body: ExplainIn) -> dict:
    """Why would (or did) this person get a yes or a no? Anyone may ask about themselves;
    Govern may simulate anyone."""
    if body.target != body.person:
        _require_govern(body.person)
    t = _person(body.target)
    result = roles.explain(t, body.action, body.value)
    if body.action in ("edit", "model", "tool", "workspace"):  # every one of these spends through the key
        info = _key_info(t["id"])
        spent, budget = float(info.get("spend") or 0), info.get("max_budget")
        live = [roles.step("Key is active, not suspended", not info.get("blocked"), "Model gateway",
                            "kill switch (/key/block)"),
                roles.step(f"Within budget: ${spent:.2f} of ${budget or 0:.2f} spent", budget is None or spent < budget,
                            "Model gateway", "max_budget on the key")]
        result = roles.decision(live + result["steps"], result["decided_by"] if result["allowed"] else "")
    result["person"] = {"id": t["id"], "name": t["name"], "level": t["level"], "grant": t["grant"]}
    return result


@app.get("/api/policy")
def policy(person: str) -> dict:
    """role.yaml as deployed, its fingerprint, and the temporary levels running now."""
    _require_govern(person)
    return {"source": roles.source(), "version": roles.version(), "grants": access.all_active()}


# --- Govern -------------------------------------------------------------------------------

def _source(log: dict) -> str:
    # Gemini CLI in a workspace speaks Gemini's own API; the app's agents use chat completions.
    return "workspace" if "generate_content" in (log.get("call_type") or "") else "app"


def _when(value) -> float:
    try:
        t = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return (t if t.tzinfo else t.replace(tzinfo=datetime.timezone.utc)).timestamp()


def _impact(rows: list[dict]) -> dict:
    """From the answers log: questions answered without a developer, and the checks behind them."""
    minutes = float(roles.config().get("roi", {}).get("minutes_per_question", 15))
    answered = [a for a in rows if not a.get("blocked") and not a.get("empty")]
    avoided = [a for a in answered if a.get("level") in ("ask", "suggest")]
    cites = sum(a.get("citations", 0) for a in answered)
    verified = sum(a.get("verified", 0) for a in answered)
    secs = [a["seconds"] for a in answered if a.get("seconds")]
    return {"answers": len(answered), "interruptions_avoided": len(avoided),
            "hours_saved": round(len(avoided) * minutes / 60, 1), "minutes_per_question": minutes,
            "citations": cites, "verified": verified, "median_seconds": round(statistics.median(secs), 1) if secs else None,
            "refused": sum(1 for a in rows if a.get("refused")), "since": rows[-1]["ts"] if rows else None}


_govern_cache = {"at": 0.0, "value": None}
_govern_lock = threading.Lock()
GOVERN_TTL = 4  # seconds; the Architecture view polls every 6 s, maybe from several tabs


def _invalidate() -> None:
    _govern_cache["at"] = 0.0


def _blocked_by_policy(err: str) -> bool:
    e = err.lower()
    return any(t in e for t in ("budget", "not allowed", "not available", "blocked", "401", "403"))


@app.get("/api/govern")
def govern(person: str) -> dict:
    _require_govern(person)
    with _govern_lock:
        if time.time() - _govern_cache["at"] > GOVERN_TTL:
            _govern_cache["value"] = _govern_data()
            _govern_cache["at"] = time.time()
        return _govern_cache["value"]


def _govern_data() -> dict:
    keys = {k.get("key_alias"): k for k in services.gateway_admin(
        "/key/list?return_full_object=true&size=100").get("keys", []) if isinstance(k, dict)}
    start = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 13 * 86400))
    end = time.strftime("%Y-%m-%d", time.gmtime(time.time() + 86400))
    logs = services.gateway_admin(f"/spend/logs?summarize=false&start_date={start}&end_date={end}")
    logs = logs if isinstance(logs, list) else logs.get("data", [])
    logs.sort(key=lambda l: _when(l.get("startTime")), reverse=True)  # newest first, whatever the gateway sends
    by_alias = {f"{p['id']}-{p['level']}": p for p in roles.people()}  # aliases use the person's own level
    now = time.time()

    per_person = collections.defaultdict(lambda: {"calls": 0, "blocked": 0, "failed": 0, "spend": 0.0, "tokens": 0,
                                                  "week": 0.0, "first": now})
    per_model = collections.defaultdict(lambda: {"calls": 0, "spend": 0.0})
    per_source = collections.defaultdict(lambda: {"calls": 0, "spend": 0.0})
    daily = collections.defaultdict(float)
    recent = []
    for log in logs:
        alias = (log.get("metadata") or {}).get("user_api_key_alias")
        if alias not in by_alias:
            continue
        p, ok = by_alias[alias], log.get("status") != "failure"
        spend, when = float(log.get("spend") or 0), _when(log.get("startTime"))
        err = str(((log.get("metadata") or {}).get("error_information") or {}).get("error_message") or "")
        row = per_person[p["id"]]
        row["calls"] += 1
        if not ok:  # a policy stop at the gateway, or something else going wrong
            row["blocked" if _blocked_by_policy(err) else "failed"] += 1
        row["spend"] += spend
        row["tokens"] += int(log.get("total_tokens") or 0)
        if now - when < 7 * 86400:
            row["week"] += spend
            row["first"] = min(row["first"], when)
        if now - when < 14 * 86400:
            daily[time.strftime("%Y-%m-%d", time.gmtime(when))] += spend
        model = log.get("model_group") or "-"
        per_model[model]["calls"] += 1
        per_model[model]["spend"] += spend
        per_source[_source(log)]["calls"] += 1
        per_source[_source(log)]["spend"] += spend
        if len(recent) < 25:
            recent.append({"id": log.get("request_id"), "pid": p["id"],
                           "time": log.get("startTime"), "person": p["name"], "level": p["level"],
                           "model": model, "source": _source(log), "ok": ok, "spend": spend,
                           "tokens": log.get("total_tokens"), "error": str(err)[:140]})

    grants = {g["person"]: g for g in access.all_active()}
    people_rows = []
    for base in roles.people():
        k, use = keys.get(f"{base['id']}-{base['level']}", {}), per_person[base["id"]]
        spent, budget = float(k.get("spend") or 0), k.get("max_budget")
        per_day = use["week"] / max(1.0, (now - use["first"]) / 86400) if use["week"] else 0.0
        days_left = (budget - spent) / per_day if per_day and budget is not None and budget > spent else None
        g = grants.get(base["id"])
        people_rows.append({"id": base["id"], "name": base["name"], "title": base["title"],
                            "level": g["level"] if g else base["level"], "base_level": base["level"],
                            "grant": g, "team": base["team"], "models": k.get("models", []),
                            "budget": budget, "spent": spent, "blocked_key": bool(k.get("blocked")),
                            "per_day": per_day, "days_left": days_left,
                            **{x: use[x] for x in ("calls", "blocked", "failed", "spend", "tokens")}})
    days = [time.strftime("%Y-%m-%d", time.gmtime(now - i * 86400)) for i in range(13, -1, -1)]
    return {"people": people_rows, "models": dict(per_model), "sources": dict(per_source),
            "daily": [{"day": d, "spend": daily.get(d, 0.0)} for d in days],
            "recent": recent, "audit": services.recent_audit(), "impact": _impact(services.answers()),
            "grants": list(grants.values()), "policy_version": roles.version()}


@app.get("/api/architecture")
def architecture(person: str) -> dict:
    """Govern data plus service health, for the live Architecture view (polled every few seconds)."""
    data = govern(person)
    data["health"] = services.health()
    data["now"] = time.time()
    return data


class BudgetIn(BaseModel):
    person: str
    target: str
    budget_usd: float = Field(ge=0, allow_inf_nan=False)


@app.post("/api/govern/budget", dependencies=[Depends(require_passcode)])
def set_budget(body: BudgetIn) -> dict:
    admin = _require_govern(body.person)
    target = _person(body.target)
    budget = round(min(MAX_BUDGET_USD, body.budget_usd), 4)
    services.key_update(target["id"], max_budget=budget)
    _invalidate()
    services.audit("budget_changed", admin["id"], "govern",
                   f"Budget for {target['name']} set to ${budget:.2f}", target=target["id"])
    return {"ok": True, "budget_usd": budget}


class SuspendIn(BaseModel):
    person: str
    target: str
    suspended: bool
    reason: str = Field(default="", max_length=300)


@app.post("/api/govern/suspend", dependencies=[Depends(require_passcode)])
def suspend(body: SuspendIn) -> dict:
    """The kill switch: block the person's key at the gateway (app and workspace), or restore it."""
    admin = _require_govern(body.person)
    target = _person(body.target)
    if target["id"] == admin["id"]:
        raise HTTPException(400, "You can't suspend your own access")
    services.key_block(target["id"], body.suspended)
    _invalidate()
    verb = "suspended" if body.suspended else "restored"
    services.audit(f"access_{verb}", admin["id"], "govern",
                   f"AI access for {target['name']} {verb}" + (f": {body.reason}" if body.reason else ""),
                   target=target["id"])
    return {"ok": True, "suspended": body.suspended}


@app.get("/api/govern/audit")
def audit_log(person: str) -> dict:
    _require_govern(person)
    events, chain = services.audit_history()
    return {"events": events[::-1], "chain": chain, "policy_version": roles.version()}


CONTROLS = [  # suggested mapping, for the customer's auditor to confirm
    {"framework": "SOC 2", "control": "CC6.1 / CC6.3", "evidence": "Role levels in role.yaml; one gateway key per person with its own models and budget"},
    {"framework": "SOC 2", "control": "CC7.2", "evidence": "Audit events for refusals, denied edits, ignored prompt injections, suspensions"},
    {"framework": "SOC 2", "control": "CC8.1", "evidence": "Suggest-level edits only as pull requests with a CI allow-list check and one human review"},
    {"framework": "ISO/IEC 27001:2022", "control": "A.5.15 / A.5.18", "evidence": "Access by level; access requests, approvals and expiry recorded"},
    {"framework": "ISO/IEC 27001:2022", "control": "A.8.2", "evidence": "Temporary elevation with an approver and automatic expiry"},
    {"framework": "ISO/IEC 27001:2022", "control": "A.8.15 / A.8.16", "evidence": "Hash-chained audit log; spend and blocked calls per person from the gateway"},
    {"framework": "ISO/IEC 27001:2022", "control": "A.8.32", "evidence": "Changes reviewed and merged by a human on GitHub"},
]


@app.get("/api/govern/evidence")
def evidence(person: str, format: Literal["json", "csv"] = "json") -> Response:
    """An evidence pack for auditors: the policy, the audit log and whether its chain is intact."""
    admin = _require_govern(person)
    events, chain = services.audit_history()
    stamp = time.strftime("%Y%m%d-%H%M", time.gmtime())
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["time_utc", "event", "person", "level", "detail", "hash", "prev_hash"])
        for e in events:
            w.writerow([e.get("ts"), e.get("kind"), e.get("person"), e.get("level"), e.get("detail"),
                        e.get("hash", ""), e.get("prev_hash", "")])
        data, mime, ext = buf.getvalue(), "text/csv", "csv"
    else:
        data = json.dumps({
            "product": "RoleSpace", "generated_at": services.now().isoformat(), "generated_by": admin["name"],
            "company": roles.config()["company"], "repository": roles.config()["repo"], "commit": agents.REPO_SHA,
            "policy": {"version": roles.version(), "role_yaml": roles.source()},
            "audit_chain": chain, "controls": CONTROLS, "events": events,
            "how_to_verify": "For each event with a hash: sha256(prev_hash + canonical JSON of the event "
                             "without ts, hash, prev_hash and id; keys sorted, separators ',' ':') == hash.",
        }, indent=2, default=str)
        mime, ext = "application/json", "json"
    services.audit("evidence_exported", admin["id"], "govern", f"Evidence pack exported ({ext}, {len(events)} events)")
    return Response(data, media_type=mime, headers={
        "Content-Disposition": f'attachment; filename="rolespace-evidence-{stamp}.{ext}"'})
