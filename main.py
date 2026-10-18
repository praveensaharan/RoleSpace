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
MAX_MEMBERS = 8            # people added through onboarding: each one is another budgeted key
SYNC_COOLDOWN = 15         # seconds between forced "Sync now" fetches of one repository
PR_LIMIT_PER_SESSION = 6   # pull requests per browser per hour
PR_LIMIT_TOTAL = 30        # and for everyone together
CHAT_LIMIT_PER_IP = 40     # per hour; the URL is public, budgets cap cost and these cap load
CHAT_LIMIT_TOTAL = 300
PASSCODE_SECRET = "demo-admin-passcode"
PASSCODE_NEEDED = "demo passcode required"
CHAT_ID = r"^[A-Za-z0-9-]{8,64}$"   # saved chats: an id the browser makes up
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


_members_at = {"t": 0.0}


def _load_members(force: bool = False) -> None:
    """People added through onboarding and policy changes made in Govern > Policy (Firestore),
    merged into role.yaml every 20 s."""
    if force or time.time() - _members_at["t"] > 20:
        try:
            roles.set_overrides(services.get_policy())
            roles.set_access(services.get_access().get("people"))
        except Exception:
            LOG.exception("could not load policy changes; keeping the last ones loaded")
        try:
            roles.set_members(services.list_members())
        except Exception:
            LOG.exception("could not load members; using role.yaml only")
        _members_at["t"] = time.time()


def _person(pid: str) -> dict:
    """The person as RoleSpace treats them now, including a temporary elevation."""
    _load_members()
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


def _session(request: Request) -> str:
    """The browser's random id (it keeps it in localStorage), or "anon"."""
    sid = request.headers.get("x-rs-session", "")
    return sid if re.fullmatch(r"[A-Za-z0-9-]{8,64}", sid) else "anon"


def _convo(request: Request, pid: str) -> str:
    """Conversations are per browser and person: the browser sends a random id it keeps."""
    return f"{_session(request)}:{pid}"


def _client_ip(request: Request) -> str:
    """Who is asking, for rate limits. The Google account IAP signed in comes first: only IAP may
    call the app, and IAP sets this header itself, so it can't be forged. Without it, the address
    the load balancer saw (it appends the client and its own address to X-Forwarded-For; earlier
    entries are whatever the caller sent, so they are never trusted)."""
    user = request.headers.get("x-goog-authenticated-user-email", "")
    if user:
        return user.split(":", 1)[-1].lower()
    hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
    if len(hops) >= 2:
        return hops[-2]
    return hops[0] if hops else (request.client.host if request.client else "?")


_pass = {"at": 0.0, "value": None}
_pass_misses: dict[str, collections.deque] = collections.defaultdict(collections.deque)


def require_passcode(request: Request) -> None:
    """Admin writes and pull requests need the demo passcode, because the demo URL is public and
    the persona switcher stands in for sign-in. Off when the secret doesn't exist (local dev)."""
    if time.time() - _pass["at"] > 300:
        try:
            _pass["value"] = services.secret(PASSCODE_SECRET)
        except gexc.NotFound:
            _pass["value"] = None
        _pass["at"] = time.time()
    code, given, ip = _pass["value"], request.headers.get("x-demo-passcode", ""), _client_ip(request)
    misses = _pass_misses[ip]
    while misses and time.time() - misses[0] > 900:
        misses.popleft()
    if len(misses) >= 10:   # guessing: 10 wrong passcodes in 15 minutes from one address
        raise HTTPException(429, "Too many wrong passcodes. Wait 15 minutes and try again.")
    if code and not hmac.compare_digest(given.encode(), code.encode()):
        if given:
            misses.append(time.time())
        raise HTTPException(401, PASSCODE_NEEDED)


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = (STATIC / "index.html").read_text().replace("__BUILD__", BUILD)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


@app.get("/health")  # Cloud Run reserves /healthz
def health() -> dict:
    return {"ok": True, "repo_commit": agents.repo_sha(), "files": len(agents.repo_files()),
            "projects": {k: agents.repo_sha(k) for k in roles.projects()},
            "policy_version": roles.version()}


@app.get("/api/status")
def status() -> dict:
    """Service health for the status light in the top bar (cached for 20 s)."""
    return {**services.health(), "commit": agents.repo_sha(), "policy_version": roles.version()}


def _viewer(request: Request) -> str | None:
    """The Google account IAP signed in, for display only (IAP sets this header on every request)."""
    email = request.headers.get("x-goog-authenticated-user-email", "")
    return email.split(":", 1)[-1] or None


@app.get("/api/people")
def people(request: Request) -> dict:
    _load_members()
    cfg = roles.config()
    out = []
    for base in roles.people():
        p = access.effective(base["id"])
        lvl = p["level_cfg"]
        out.append({k: p[k] for k in ("id", "name", "title", "team", "level", "base_level", "grant", "email")} | {
            "models": roles.person_models(p), "budget_usd": lvl["budget_usd"], "tools": lvl["tools"],
            "allow_paths": lvl.get("allow_paths", []), "agent_model": agents.pick_model(p, None),
            "projects": roles.person_projects(p), "onboarded": bool(p.get("created_by")),
            "elevation_targets": roles.elevation_targets(p["base_level"])})
    levels = {k: {"models": v["models"], "budget_usd": v["budget_usd"], "tools": v["tools"],
                  "allow_paths": v.get("allow_paths", []), "deny_paths": v.get("deny_paths", []),
                  "rpm_limit": v.get("rpm_limit"), "tpm_limit": v.get("tpm_limit")}
              for k, v in cfg["levels"].items()}
    return {"company": cfg["company"], "repo": cfg["repo"], "commit": agents.repo_sha(),
            "budget_period": cfg["budget_period"], "people": out, "levels": levels,
            "teams": cfg.get("teams", {}), "elevation": cfg.get("elevation", {}),
            "policy_version": roles.version(), "files": list(agents.repo_files()), "viewer": _viewer(request),
            "catalog": roles.catalog(), "company_domain": cfg.get("company_domain"),
            "projects": {k: {**v, "commit": agents.repo_sha(k), "files": len(agents.repo_files(k)),
                             "pull_requests": roles.project_prs(k)} for k, v in roles.projects().items()}}


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
    model: str | None = Field(default=None, max_length=60)      # must be on the person's list
    project: str | None = Field(default=None, max_length=60)
    chat: str | None = Field(default=None, pattern=CHAT_ID)       # saved chat to add this turn to


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
    _load_members()
    try:
        roles.person(body.person)
    except KeyError:
        raise HTTPException(404, f"unknown person {body.person}")
    _rate_limit(_client_ip(request))
    key, sid, question = _convo(request, body.person), _session(request), body.message.strip()[:4000]
    async with _chat_locks[key]:  # one turn at a time per conversation: one ADK session each
        p = await run_in_threadpool(_person, body.person)
        result = await agents.chat(p, question, key, body.model, body.project)
        if body.chat and sid != "anon":
            try:
                result["saved"] = await run_in_threadpool(services.save_turn, body.chat, sid, p["id"], question, result)
            except Exception:
                LOG.exception("could not save the chat turn")  # the answer still goes back
                result["saved"] = False
    try:
        await run_in_threadpool(services.log_answer, {
            "person": p["id"], "level": p["level"], "model": result["model"], "seconds": result["seconds"],
            "project": result["project"],
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


# --- Saved chats: per browser and person, kept 30 days after last use ---------------------

def _chat_id(cid: str) -> str:
    if not re.fullmatch(CHAT_ID, cid):
        raise HTTPException(400, "bad chat id")
    return cid


@app.get("/api/chats")
def chats(person: str, request: Request) -> dict:
    """This browser's saved chats for the person, newest first."""
    sid = _session(request)
    return {"chats": [] if sid == "anon" else services.list_chats(sid, _person(person)["id"]),
            "keep_days": services.CHAT_DAYS}


@app.post("/api/chats/{cid}/open")
def open_chat(cid: str, body: PersonIn, request: Request) -> dict:
    """Load a saved chat and carry on with it: the model gets its last few turns as context.
    Edit previews this server no longer holds come back marked expired."""
    p, sid = _person(body.person), _session(request)
    c = services.get_chat(_chat_id(cid), sid, p["id"]) if sid != "anon" else None
    if not c:
        raise HTTPException(404, "This chat isn't saved in this browser")
    live = agents.resume(_convo(request, p["id"]), c["turns"])
    for t in c["turns"]:
        for e in t["r"].get("edits") or []:
            e["expired"] = e["id"] not in live
    return {"id": cid, "title": c.get("title", ""), "turns": c["turns"]}


@app.post("/api/chats/{cid}/delete")
def delete_chat(cid: str, body: PersonIn, request: Request) -> dict:
    p, sid = _person(body.person), _session(request)
    if sid == "anon" or not services.delete_chat(_chat_id(cid), sid, p["id"]):
        raise HTTPException(404, "This chat isn't saved in this browser")
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
    # Checked again here, not only in the agent's tool: this is the call that writes. Pull requests
    # go to the one repository the GitHub token and the allow-list CI check cover.
    project = edit.get("project", agents.DEFAULT_PROJECT)
    if not roles.project_prs(project) or agents.repo_name(project) != services.GITHUB_REPO:
        services.audit("edit_denied", p["id"], p["level"], f"PR for {edit['path']} in {project} denied at open")
        raise HTTPException(403, f"RoleSpace doesn't open pull requests in {project}")
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
        title = edit["reason"][:80]
        body_md = (f"Change by **{p['name']}** ({p['title']}), who reviewed it before opening this pull "
                   f"request. They have no GitHub account, so it was opened for them; they follow its "
                   f"checks, review and comments in RoleSpace.\n\n"
                   f"> {edit['reason']}\n\nOnly `{edit['path']}` changes. The `designer-allowlist` check and one "
                   f"human review are required before merge.\n\nPolicy version `{roles.version()}`.")
        url = services.open_pr(branch, edit["path"], edit["old_text"], edit["new_text"], title, body_md,
                               author=(p["name"], p.get("email") or f"{p['id']}@users.noreply.rolespace"))
    finally:
        _pr_inflight.discard(body.edit_id)
    agents.drop_edit(key, body.edit_id)  # only once the PR exists; a failure keeps the preview
    _gh_activity.pop(project, None)   # the new pull request shows up in Issues & pull requests at once
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
    project: str | None = Field(default=None, max_length=60)


@app.post("/api/policy/explain")
def policy_explain(body: ExplainIn) -> dict:
    """Why would (or did) this person get a yes or a no? Anyone may ask about themselves;
    Govern may simulate anyone."""
    if body.target != body.person:
        _require_govern(body.person)
    t = _person(body.target)
    result = roles.explain(t, body.action, body.value, body.project if body.project in roles.projects() else None)
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
    """role.yaml as deployed, the admin's changes on top of it, the fingerprint of both, and the
    temporary levels running now."""
    _require_govern(person)
    saved = services.get_policy()
    return {"source": roles.source(), "version": roles.version(), "grants": access.all_active(),
            "overrides": roles.overrides(), "changed_by": saved.get("by") if roles.overrides() else None,
            "changed_at": services._iso(saved.get("ts")) if roles.overrides() else None,
            "limits": roles.LIMITS}


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
                            "onboarded": bool(base.get("created_by")), "email": base.get("email", ""),
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


# --- GitHub: a repository's issues and pull requests, for people without GitHub accounts ---

_gh_activity: dict[str, tuple[float, dict]] = {}


@app.get("/api/github")
def github_activity(person: str, project: str) -> dict:
    """Open issues and recent pull requests of a repository this person can access, live from
    GitHub (cached for a minute). Read-only: nobody needs a GitHub account to follow the work."""
    p = _person(person)
    if project not in roles.person_projects(p):
        raise HTTPException(403, f"{p['name']} has no access to {project}")
    hit = _gh_activity.get(project)
    if hit and time.time() - hit[0] < 60:
        return hit[1]
    repo = agents.repo_name(project)
    issues = [i for i in services.github_list(repo, "/issues?state=open&per_page=50&sort=updated")
              if "pull_request" not in i]
    pulls = services.github_list(repo, "/pulls?state=all&per_page=30&sort=updated&direction=desc")
    out = {
        "project": project, "repo": repo, "fetched": time.time(),
        "issues": [{"number": i["number"], "title": i["title"], "url": i["html_url"],
                    "author": (i.get("user") or {}).get("login"), "comments": i.get("comments", 0),
                    "labels": [{"name": x["name"], "color": x.get("color", "e5e7eb")} for x in i.get("labels", [])],
                    "created": i.get("created_at"), "updated": i.get("updated_at")} for i in issues],
        "pulls": [{"number": x["number"], "title": x["title"], "url": x["html_url"],
                   "author": (x.get("user") or {}).get("login"), "draft": x.get("draft", False),
                   "state": "merged" if x.get("merged_at") else x["state"], "branch": x["head"]["ref"],
                   "from_rolespace": x["head"]["ref"].startswith("rolespace/"),
                   "created": x.get("created_at"), "updated": x.get("updated_at")} for x in pulls],
    }
    _gh_activity[project] = (time.time(), out)
    return out


# --- Govern: reset the demo for the next judge --------------------------------------------

@app.post("/api/govern/demo-reset", dependencies=[Depends(require_passcode)])
def demo_reset(body: PersonIn) -> dict:
    """Put the demo back the way it started: policy and repo access from role.yaml, every
    role.yaml person active on their level's models and budget with spend back to zero,
    temporary access ended, people added during the demo removed. The gateway's own total
    budget (gateway/config.yaml) is not touched: nothing here can raise the ceiling."""
    admin = _require_govern(body.person)
    _load_members(force=True)
    steps, failed = [], []
    for g in access.all_active():
        try:
            access.end(g["person"], admin["id"], "revoked")
        except Exception:
            failed.append(f"end temporary access for {g['person']}")
    removed = 0
    for m in services.list_members():
        if m.get("status", "active") == "active":
            try:
                services.key_block(m["id"], True)
                services.update_member(m["id"], status="removed", removed_by=admin["id"])
                removed += 1
            except Exception:
                failed.append(f"remove {m['id']}")
    services.save_policy({}, admin["id"])
    services.save_access({}, admin["id"])
    roles.set_overrides({})
    roles.set_access({})
    _load_members(force=True)
    for p in roles.config()["people"]:
        person, lvl = roles.person(p["id"]), roles.config()["levels"][p["level"]]
        try:
            services.key_update(p["id"], models=roles.person_models(person), max_budget=lvl["budget_usd"], spend=0,
                                **{k: lvl[k] for k in ("rpm_limit", "tpm_limit") if lvl.get(k)})
            services.key_block(p["id"], False)
        except Exception:
            LOG.exception("demo reset: key for %s", p["id"])
            failed.append(f"reset the key for {p['name']}")
    steps = ["Policy and repo access back to role.yaml",
             f"{len(roles.config()['people'])} people active on their level's models and budget, spend back to $0",
             "Temporary access ended", f"{removed} people added during the demo removed (keys blocked)",
             "The gateway's total budget is unchanged"]
    services.audit("demo_reset", admin["id"], "govern", "Demo reset: " + "; ".join(steps[:4]),
                   failed=failed, version=roles.version())
    _invalidate()
    return {"steps": steps, "failed": failed}


# --- Govern: repo access (who may ask about and work on which repository) -----------------

def _access_view() -> dict:
    saved = services.get_access()
    projects = {k: {"name": v.get("name", k), "repo": v["repo"], "team": v.get("team"),
                    "owner": roles.team_owner(v.get("team") or ""), "pull_requests": roles.project_prs(k),
                    "commit": agents.repo_sha(k), "files": len(agents.repo_files(k)),
                    "checked": agents.checked_at(k)}
                for k, v in roles.projects().items()}
    people = [{"id": p["id"], "name": p["name"], "title": p.get("title", ""), "team": p["team"],
               "email": p.get("email", ""), "level": p["level"], "onboarded": bool(p.get("created_by")),
               "projects": roles.person_projects(p), "default": roles.default_projects(p),
               "changed": p["id"] in roles.access()} for p in roles.people()]
    return {"projects": projects, "people": people, "changed_by": saved.get("by"),
            "changed_at": services._iso(saved.get("ts")) if saved else None}


@app.get("/api/govern/access")
def repo_access(person: str) -> dict:
    _require_govern(person)
    _load_members(force=True)
    return _access_view()


@app.post("/api/govern/repos/{project}/sync")
def sync_repo(project: str, body: PersonIn) -> dict:
    """Fetch the newest main of one repository now. Answers do this on their own, at most once a
    minute per repository; this is for an admin who just merged something."""
    _require_govern(body.person)
    if project not in roles.projects():
        raise HTTPException(404, f"unknown repository {project}")
    last = agents.checked_at(project)
    if last and time.time() - last < SYNC_COOLDOWN:
        raise HTTPException(429, f"Checked {int(time.time() - last)} s ago; try again in a few seconds")
    result = agents.sync_project(project, force=True)
    _invalidate()
    return {"sync": result, **_access_view()}


class AccessChangeIn(BaseModel):
    person: str
    people: dict[str, list[str]] = Field(max_length=200)   # person id -> projects, for the people changed


@app.post("/api/govern/access", dependencies=[Depends(require_passcode)])
def save_repo_access(body: AccessChangeIn) -> dict:
    """Give or take away repositories. The assistant follows at once; Build workspaces clone the
    new list at their next start once coder/sync_build_keys.sh has run."""
    admin = _require_govern(body.person)
    _load_members(force=True)
    everyone = {p["id"]: p for p in roles.people()}
    errors = roles.validate_access(body.people, set(everyone))
    if errors:
        raise HTTPException(400, " ".join(errors[:5]))
    name = lambda k: roles.projects()[k].get("name", k)  # noqa: E731
    stored, changes = roles.access(), []
    for pid, picked in body.people.items():
        p, before = everyone[pid], roles.person_projects(everyone[pid])
        added, removed = [x for x in picked if x not in before], [x for x in before if x not in picked]
        if added or removed:
            changes.append(f"{p['name']}: " + "; ".join(
                ([f"+ {', '.join(map(name, added))}"] if added else []) + ([f"− {', '.join(map(name, removed))}"] if removed else [])))
        if sorted(picked) == sorted(roles.default_projects(p)):
            stored.pop(pid, None)   # back to what role.yaml or onboarding says: nothing to keep
        else:
            stored[pid] = [x for x in roles.projects() if x in picked]   # in role.yaml's order
    if not changes:
        return {"changes": [], **_access_view()}
    services.save_access(stored, admin["id"])
    roles.set_access(stored)
    services.audit("repo_access_changed", admin["id"], "govern", "Repo access: " + " | ".join(changes),
                   changes=changes, version=roles.version())
    _invalidate()
    return {"changes": changes, **_access_view()}


# --- Govern: the policy form (each level's models, budget and limits, without YAML) -------

class LevelPolicyIn(BaseModel):
    models: list[str] = Field(max_length=20)
    budget_usd: float = Field(allow_inf_nan=False)
    rpm_limit: int
    tpm_limit: int


class PolicyIn(BaseModel):
    person: str
    levels: dict[str, LevelPolicyIn] = Field(max_length=10)
    models: dict[str, Literal["enabled", "available"]] = Field(max_length=40)


def _sync_keys(budget_levels: set[str]) -> tuple[list[str], list[str]]:
    """Push the policy in force to every person's gateway key: models and rate limits always,
    and the level's budget for people whose level's budget just changed."""
    updated, failed = [], []
    for base in roles.people():
        pid, lvl = base["id"], base["level_cfg"]
        try:
            g = access.active(pid)
            fields = {"models": access.key_models(pid, g["level"] if g else None)}
            fields.update({k: lvl[k] for k in ("rpm_limit", "tpm_limit") if lvl.get(k)})
            if base["level"] in budget_levels:
                fields["max_budget"] = lvl["budget_usd"]
            services.key_update(pid, **fields)
            updated.append(base["name"])
        except Exception:
            LOG.exception("could not update the gateway key for %s", pid)
            failed.append(base["name"])
    return updated, failed


def _apply_policy(admin: dict, stored: dict, kind: str) -> dict:
    """Save the admin's changes, put them in force, and push them to every key."""
    before, after = roles.config(), roles.merged(stored)
    changes = roles.describe_changes(before, after)
    if not changes and stored == roles.overrides():   # nothing new: just retry pushing it to the keys
        updated, failed = _sync_keys(set())
        return {"changes": [], "updated": updated, "failed": failed, "version": roles.version()}
    services.save_policy(stored, admin["id"])   # recorded first: keys never run ahead of the record
    roles.set_overrides(stored)
    budgets = {k for k, v in after["levels"].items() if v["budget_usd"] != before["levels"][k]["budget_usd"]}
    updated, failed = _sync_keys(budgets)
    summary = "; ".join(changes) or "no change in effect"
    services.audit(kind, admin["id"], "govern",
                   ("Policy back to role.yaml: " if kind == "policy_reset" else "Policy changed: ") + summary,
                   changes=changes, version=roles.version(), keys_failed=failed)
    _invalidate()
    return {"changes": changes, "updated": updated, "failed": failed, "version": roles.version()}


@app.post("/api/govern/policy", dependencies=[Depends(require_passcode)])
def save_policy(body: PolicyIn) -> dict:
    admin = _require_govern(body.person)
    _load_members(force=True)
    levels = {k: v.model_dump() for k, v in body.levels.items()}
    errors = roles.validate_policy(levels, body.models)
    if errors:
        raise HTTPException(400, " ".join(errors[:5]))
    return _apply_policy(admin, roles.minimal(levels, body.models), "policy_changed")


@app.post("/api/govern/policy/sync", dependencies=[Depends(require_passcode)])
def sync_policy(body: PersonIn) -> dict:
    """Push the policy in force to every key again (models and limits; budgets stay as they are):
    after a failed save, or after provision_keys.py wrote role.yaml's values over the app's."""
    admin = _require_govern(body.person)
    _load_members(force=True)
    updated, failed = _sync_keys(set())
    services.audit("policy_synced", admin["id"], "govern",
                   f"Policy {roles.version()} pushed to {len(updated)} gateway keys" + (f"; failed: {', '.join(failed)}" if failed else ""),
                   version=roles.version(), keys_failed=failed)
    _invalidate()
    return {"updated": updated, "failed": failed, "version": roles.version()}


@app.post("/api/govern/policy/reset", dependencies=[Depends(require_passcode)])
def reset_policy(body: PersonIn) -> dict:
    """Drop every change made in the app: role.yaml alone decides again."""
    admin = _require_govern(body.person)
    _load_members(force=True)
    return _apply_policy(admin, {}, "policy_reset")


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
            "company": roles.config()["company"], "repository": roles.config()["repo"], "commit": agents.repo_sha(),
            "policy": {"version": roles.version(), "role_yaml": roles.source()},
            "audit_chain": chain, "controls": CONTROLS, "events": events,
            "how_to_verify": "For each event with a hash: sha256(prev_hash + canonical JSON of the event "
                             "without ts, hash, prev_hash and id; keys sorted, separators ',' ':') == hash.",
        }, indent=2, default=str)
        mime, ext = "application/json", "json"
    services.audit("evidence_exported", admin["id"], "govern", f"Evidence pack exported ({ext}, {len(events)} events)")
    return Response(data, media_type=mime, headers={
        "Content-Disposition": f'attachment; filename="rolespace-evidence-{stamp}.{ext}"'})


# --- Changes: pull requests opened through RoleSpace, for people without GitHub accounts ----

@app.get("/api/changes")
def changes(person: str) -> dict:
    """Each pull request RoleSpace opened for this person (all of them for Govern), with where
    it stands on GitHub: checks, review, merged or not."""
    viewer = _person(person)
    events = [e for e in services.recent_audit(300) if e.get("kind") == "pr_opened" and e.get("url")]
    if viewer["level"] != "govern":
        events = [e for e in events if e.get("person") == viewer["id"]]
    out = []
    for e in events[:20]:
        item = {"url": e["url"], "person": e["person"], "name": _name(e["person"]), "opened": e["ts"],
                "detail": e.get("detail", "")}
        m = re.search(r"/pull/(\d+)", e["url"])
        if m:
            try:
                item.update(services.pr_status(int(m.group(1))))
            except services.UpstreamError as err:
                item["error"] = str(err)
        out.append(item)
    return {"changes": out}


# --- Usage: tokens and cost by person, model, project and source ---------------------------

def _usage_rows(days: int) -> list[dict]:
    now = time.time()
    start = time.strftime("%Y-%m-%d", time.gmtime(now - (days - 1) * 86400))
    end = time.strftime("%Y-%m-%d", time.gmtime(now + 86400))
    logs = services.gateway_admin(f"/spend/logs?summarize=false&start_date={start}&end_date={end}")
    logs = logs if isinstance(logs, list) else logs.get("data", [])
    by_alias = {f"{p['id']}-{p['base_level']}": p for p in roles.people()}
    rows = []
    for log in logs:
        p = by_alias.get((log.get("metadata") or {}).get("user_api_key_alias"))
        if not p:
            continue
        tags = dict(t.split(":", 1) for t in (log.get("request_tags") or [])
                    if isinstance(t, str) and ":" in t and not t.startswith("User-Agent"))
        # The person comes from the key, so it can't be faked. Tags are only a claim (a workspace
        # could send its own), so a project counts only if it's one of the person's.
        mine = roles.person_projects(p)
        project = tags.get("project")
        if project not in mine:
            project = mine[0] if len(mine) == 1 else "unattributed"
        when = _when(log.get("startTime"))
        rows.append({"time": log.get("startTime"), "day": time.strftime("%Y-%m-%d", time.gmtime(when)),
                     "person": p["id"], "name": p["name"], "level": p["base_level"],
                     "model": log.get("model_group") or "-", "project": project,
                     "source": "workspace" if "workspace" in (_source(log), tags.get("source")) else "app",
                     "prompt_tokens": int(log.get("prompt_tokens") or 0),
                     "completion_tokens": int(log.get("completion_tokens") or 0),
                     "spend": float(log.get("spend") or 0), "ok": log.get("status") != "failure"})
    return rows


def _sum(rows: list[dict]) -> dict:
    return {"calls": len(rows), "prompt_tokens": sum(r["prompt_tokens"] for r in rows),
            "completion_tokens": sum(r["completion_tokens"] for r in rows),
            "spend": round(sum(r["spend"] for r in rows), 6), "failed": sum(1 for r in rows if not r["ok"])}


def _group(rows: list[dict], key: str) -> dict:
    groups = collections.defaultdict(list)
    for r in rows:
        groups[r[key]].append(r)
    return {k: _sum(v) for k, v in sorted(groups.items(), key=lambda kv: -sum(r["spend"] for r in kv[1]))}


@app.get("/api/govern/usage")
def usage(person: str, days: int = 14) -> dict:
    """Token and cost tracking from the gateway's spend log, with each person's limits."""
    _require_govern(person)
    days = max(1, min(30, days))
    rows = _usage_rows(days)
    keys = {k.get("key_alias"): k for k in services.gateway_admin(
        "/key/list?return_full_object=true&size=100").get("keys", []) if isinstance(k, dict)}
    people_out = []
    for p in roles.people():
        mine = [r for r in rows if r["person"] == p["id"]]
        k = keys.get(f"{p['id']}-{p['base_level']}", {})
        people_out.append({"id": p["id"], "name": p["name"], "level": p["base_level"], **_sum(mine),
                           "models": _group(mine, "model"), "budget": k.get("max_budget"),
                           "spent_period": k.get("spend", 0.0), "rpm_limit": k.get("rpm_limit"),
                           "tpm_limit": k.get("tpm_limit"), "blocked": bool(k.get("blocked"))})
    daily = collections.defaultdict(lambda: collections.defaultdict(float))
    for r in rows:
        daily[r["day"]][r["model"]] += r["prompt_tokens"] + r["completion_tokens"]
    days_list = [time.strftime("%Y-%m-%d", time.gmtime(time.time() - i * 86400)) for i in range(days - 1, -1, -1)]
    return {"days": days, "totals": _sum(rows), "people": people_out, "models": _group(rows, "model"),
            "projects": _group(rows, "project"), "sources": _group(rows, "source"),
            "daily": [{"day": d, "tokens": dict(daily.get(d, {}))} for d in days_list],
            "catalog": roles.catalog()}


@app.get("/api/govern/usage.csv")
def usage_csv(person: str, days: int = 30) -> Response:
    _require_govern(person)
    rows = _usage_rows(max(1, min(30, days)))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["time", "person", "name", "level", "project", "source", "model",
                                        "prompt_tokens", "completion_tokens", "spend", "ok"], extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return Response(buf.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="rolespace-usage-{time.strftime("%Y%m%d")}.csv"'})


# --- Onboarding: a Govern admin adds a person by email --------------------------------------

class MemberIn(BaseModel):
    person: str
    email: str = Field(max_length=120)
    name: str = Field(max_length=80)
    title: str = Field(default="", max_length=80)
    team: str = Field(max_length=40)
    level: str = Field(max_length=20)
    projects: list[str] = Field(default_factory=list, max_length=20)
    models: list[str] = Field(default_factory=list, max_length=10)
    budget_usd: float = Field(ge=0, le=MAX_BUDGET_USD, allow_inf_nan=False)


@app.post("/api/govern/members", dependencies=[Depends(require_passcode)])
def add_member(body: MemberIn) -> dict:
    """Create the person's gateway key (their models, budget and limits), store it in Secret
    Manager, and add them to RoleSpace. Build-level workspaces are queued for the Coder VM."""
    admin = _require_govern(body.person)
    _load_members(force=True)
    active = [x for x in services.list_members() if x.get("status", "active") == "active"]
    if len(active) >= MAX_MEMBERS:
        raise HTTPException(409, f"This demo allows {MAX_MEMBERS} added people; remove one first. Each person is "
                                 "another budgeted gateway key, and the gateway's total budget caps them all.")
    m = body.model_dump(exclude={"person"})
    m.update(email=m["email"].strip().lower(), name=m["name"].strip(), title=m["title"].strip())
    errors = roles.validate_member(m)
    if errors:
        raise HTTPException(400, " ".join(errors))
    mid, cfg = roles.member_id(m["email"]), roles.config()
    secret_name, lvl = f"gw-key-{mid}", cfg["levels"][m["level"]]
    try:
        services.ensure_secret(secret_name)   # before the key exists: never mint a key we can't keep
    except gexc.PermissionDenied:
        raise HTTPException(403, "RoleSpace's service account can't create secrets yet. Grant it Secret "
                                 "Manager Admin limited to secrets named gw-key-* (docs/setup-gcp.md). "
                                 "Nothing was created.")
    try:
        services.gateway_admin("/user/new", {"user_id": m["email"], "user_email": m["email"],
                                             "user_alias": m["name"], "user_role": "internal_user",
                                             "auto_create_key": False})
    except services.UpstreamError:
        pass   # already a gateway user
    alias = f"{mid}-{m['level']}"
    stale = services.key_info(alias)   # aliases are unique at the gateway
    if stale.get("token") and not stale.get("blocked"):
        raise HTTPException(409, f"A live gateway key named {alias} already exists. Nothing was created.")
    if stale.get("token"):   # left blocked when someone with this id was removed earlier
        services.gateway_admin("/key/delete", {"keys": [stale["token"]]})
    settings = {"user_id": m["email"], "key_alias": alias, "models": m["models"],
                "max_budget": m["budget_usd"], "budget_duration": cfg["budget_period"],
                "allowed_routes": ["llm_api_routes"],
                "metadata": {"person": mid, "level": m["level"], "team": m["team"], "projects": m["projects"]}}
    settings.update({k: lvl[k] for k in ("rpm_limit", "tpm_limit") if lvl.get(k)})
    key = services.gateway_admin("/key/generate", settings)["key"]
    try:
        services.add_secret_version(secret_name, key)
    except Exception:
        services.gateway_admin("/key/delete", {"keys": [key]})   # don't leave a key nobody holds
        raise
    member = {**m, "id": mid, "status": "active", "created_by": admin["id"],
              "workspace": "queued" if m["level"] == "build" else "none"}
    services.save_member(member)
    services.audit("member_added", admin["id"], "govern",
                   f"{m['name']} ({m['email']}) added at {m['level']} level; projects {', '.join(m['projects'])}; "
                   f"models {', '.join(m['models'])}; budget ${m['budget_usd']:.2f}", target=mid)
    _load_members(force=True)
    _invalidate()
    steps = [f"Gateway key {mid}-{m['level']}: {', '.join(m['models'])}, ${m['budget_usd']:.2f} per "
             f"{cfg['budget_period']}, model routes only",
             f"Key stored in Secret Manager as {secret_name}",
             f"Projects: {', '.join(cfg['projects'][x]['name'] for x in m['projects'])}",
             "They sign in with Google and find their level, tools and budget waiting"]
    if m["level"] == "build":
        steps.append("Coder workspace queued: run coder/sync_build_keys.sh to hand the key to the workspace VM")
    return {"id": mid, "steps": steps}


@app.post("/api/govern/members/{mid}/remove", dependencies=[Depends(require_passcode)])
def remove_member(mid: str, body: PersonIn) -> dict:
    """Offboarding: block the person's key at the gateway and take them out of RoleSpace."""
    admin = _require_govern(body.person)
    if any(p["id"] == mid for p in roles.config()["people"]):
        raise HTTPException(400, "People listed in role.yaml are removed by editing role.yaml")
    member = next((x for x in services.list_members() if x["id"] == mid and x.get("status") == "active"), None)
    if not member:
        raise HTTPException(404, "No such member")
    services.key_block(mid, True)
    services.update_member(mid, status="removed", removed_by=admin["id"])
    services.audit("member_removed", admin["id"], "govern", f"{member['name']} removed; key blocked", target=mid)
    _load_members(force=True)
    _invalidate()
    return {"ok": True}
