"""Google Cloud and GitHub plumbing: secrets, the gateway, the audit log, requests, grants,
answers and pull requests."""

import base64
import datetime
import hashlib
import json
import os
import subprocess
import threading
import time
from functools import lru_cache

import httpx
from google.cloud import firestore, secretmanager
from google.cloud.firestore_v1.base_query import FieldFilter

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-c399f432-18ea-45d7-b98")
GATEWAY_URL = os.environ.get("GATEWAY_URL", "https://rs-gateway-894526891132.us-central1.run.app")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "praveensaharan/firstround-demo")


class UpstreamError(Exception):
    """A dependency (gateway, GitHub) said no or didn't answer. The message is safe to show."""


def now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


# --- Secrets ---------------------------------------------------------------------------

@lru_cache
def _sm() -> secretmanager.SecretManagerServiceClient:
    return secretmanager.SecretManagerServiceClient()


_secrets: dict[str, tuple[float, str]] = {}
SECRET_TTL = 600  # re-read every 10 minutes, so a rotated token or key is picked up


def secret(name: str) -> str:
    hit = _secrets.get(name)
    if hit and time.time() - hit[0] < SECRET_TTL:
        return hit[1]
    path = f"projects/{PROJECT}/secrets/{name}/versions/latest"
    value = _sm().access_secret_version(name=path).payload.data.decode().strip()
    _secrets[name] = (time.time(), value)
    return value


def person_key(pid: str) -> str:
    """Each person's own gateway key. The app never calls Gemini with anything else."""
    return secret(f"gw-key-{pid}")


def ensure_secret(name: str) -> None:
    """Create an empty secret if it doesn't exist. Raises PermissionDenied when this identity
    may not create secrets; onboarding calls it first, so no key is minted that can't be stored."""
    from google.api_core import exceptions as gexc
    try:
        _sm().create_secret(request={"parent": f"projects/{PROJECT}", "secret_id": name,
                                     "secret": {"replication": {"automatic": {}}}})
    except gexc.AlreadyExists:
        pass


def add_secret_version(name: str, value: str) -> None:
    _sm().add_secret_version(request={"parent": f"projects/{PROJECT}/secrets/{name}",
                                      "payload": {"data": value.encode()}})
    _secrets.pop(name, None)


# --- Gateway ---------------------------------------------------------------------------

_token = {"value": "", "expires": 0.0}
_token_lock = threading.Lock()


def id_token() -> str:
    """Google ID token for Cloud Run IAM on the gateway (it has no public invokers)."""
    with _token_lock:
        if time.time() > _token["expires"]:
            if os.environ.get("K_SERVICE"):  # on Cloud Run: the service account
                import google.auth.transport.requests
                import google.oauth2.id_token
                value = google.oauth2.id_token.fetch_id_token(
                    google.auth.transport.requests.Request(), GATEWAY_URL)
            else:  # local development: your own gcloud sign-in
                value = subprocess.run(["gcloud", "auth", "print-identity-token"], check=True,
                                       capture_output=True, text=True).stdout.strip()
            _token.update(value=value, expires=time.time() + 45 * 60)
        return _token["value"]


def iam_header() -> dict:
    # Cloud Run reads IAM from X-Serverless-Authorization, so Authorization stays free for
    # the LiteLLM key.
    return {"X-Serverless-Authorization": f"Bearer {id_token()}"}


_http = httpx.Client(base_url=GATEWAY_URL, timeout=30)  # pooled connections for admin calls


def gateway_admin(path: str, body: dict | None = None) -> dict | list:
    headers = {"Authorization": f"Bearer {secret('litellm-master-key')}", **iam_header()}
    try:
        r = _http.post(path, json=body, headers=headers) if body is not None else _http.get(path, headers=headers)
    except httpx.HTTPError as e:
        raise UpstreamError(f"Model gateway didn't answer ({type(e).__name__})") from e
    if r.status_code >= 400:
        raise UpstreamError(f"Model gateway refused {path.split('?')[0]}: HTTP {r.status_code} {r.text[:160]}")
    return r.json()


def key_info(alias: str) -> dict:
    """A person's key as the gateway sees it, found by alias: the key itself never goes in a URL
    (URLs end up in request logs)."""
    keys = gateway_admin(f"/key/list?key_alias={alias}&return_full_object=true&size=5").get("keys", [])
    return next((k for k in keys if isinstance(k, dict) and k.get("key_alias") == alias), {})


def key_update(pid: str, **fields) -> None:
    gateway_admin("/key/update", {"key": person_key(pid), **fields})


def key_block(pid: str, blocked: bool) -> None:
    """The kill switch: a blocked key stops every model call, from the app and from workspaces."""
    gateway_admin("/key/block" if blocked else "/key/unblock", {"key": person_key(pid)})


_health = {"at": 0.0, "value": {}}


def health(max_age: float = 20) -> dict:
    """Is the gateway answering, and is the Coder VM running? Never fails; cached for 20 s."""
    if time.time() - _health["at"] < max_age:
        return _health["value"]
    out = {}
    try:
        r = httpx.get(f"{GATEWAY_URL}/health/liveliness", headers=iam_header(), timeout=5)
        out["gateway"] = "up" if r.status_code == 200 else f"http {r.status_code}"
    except Exception as e:
        out["gateway"] = f"down ({type(e).__name__})"
    try:
        import google.auth
        import google.auth.transport.requests
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        session = google.auth.transport.requests.AuthorizedSession(creds)
        r = session.get(f"https://compute.googleapis.com/compute/v1/projects/{PROJECT}/zones/"
                        f"us-central1-a/instances/coder-vm?fields=status", timeout=5)
        out["coder_vm"] = r.json().get("status", f"http {r.status_code}") if r.ok else f"http {r.status_code}"
    except Exception as e:
        out["coder_vm"] = f"unknown ({type(e).__name__})"
    _health.update(at=time.time(), value=out)
    return out


# --- Firestore -------------------------------------------------------------------------

@lru_cache
def _db() -> firestore.Client:
    return firestore.Client(project=PROJECT)


# Test runs (eval, local checks) set RS_COLLECTION_PREFIX=eval_ so they never touch the live
# audit chain, inbox or impact numbers.
PREFIX = os.environ.get("RS_COLLECTION_PREFIX", "")


def _col(name: str) -> firestore.CollectionReference:
    return _db().collection(PREFIX + name)


def _iso(value) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value or "")


def _docs(collection: str, limit: int, newest_first: bool = True) -> list[dict]:
    direction = firestore.Query.DESCENDING if newest_first else firestore.Query.ASCENDING
    q = _col(collection).order_by("ts", direction=direction).limit(limit)
    return [{**d.to_dict(), "id": d.id} for d in q.stream()]


# --- Audit log: append-only, hash-chained ----------------------------------------------
# Each event stores the hash of the one before it, so a later edit or deletion breaks the
# chain and verify_chain() says where. One app instance writes, under a lock.

GENESIS = "0" * 64
_audit_lock = threading.Lock()
_chain = {"head": None}


def _canonical(rec: dict) -> str:
    return json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _event_hash(prev: str, rec: dict) -> str:
    return hashlib.sha256((prev + _canonical(rec)).encode()).hexdigest()


def audit(kind: str, person: str, level: str, detail: str, **extra) -> None:
    """kind: refused_change | edit_denied | tool_denied | injection_ignored | edit_previewed |
    pr_opened | budget_changed | access_suspended | access_restored | access_requested |
    elevation_granted | elevation_denied | elevation_ended | request_updated | policy_changed |
    policy_reset | policy_synced | repo_access_changed | demo_reset"""
    with _audit_lock:
        if _chain["head"] is None:
            latest = next((e for e in _docs("audit", 50) if e.get("hash")), None)
            _chain["head"] = latest["hash"] if latest else GENESIS
        ts = now()
        rec = {"ts_iso": ts.isoformat(), "kind": kind, "person": person, "level": level,
               "detail": detail[:500], **extra}
        digest = _event_hash(_chain["head"], rec)
        _col("audit").add({**rec, "ts": ts, "prev_hash": _chain["head"], "hash": digest})
        _chain["head"] = digest


def _public(e: dict) -> dict:
    return {**e, "ts": _iso(e.get("ts"))}


def recent_audit(limit: int = 60) -> list[dict]:
    return [_public(e) for e in _docs("audit", limit)]


def verify_chain(events_oldest_first: list[dict]) -> dict:
    """Recompute every hash. Events from before the chain existed are counted, not checked."""
    prev, checked, legacy = None, 0, 0
    for e in events_oldest_first:
        if not e.get("hash"):
            legacy += 1
            continue
        rec = {k: v for k, v in e.items() if k not in ("ts", "hash", "prev_hash", "id")}
        if prev is not None and e.get("prev_hash") != prev:
            return {"ok": False, "checked": checked, "legacy": legacy, "event": e["id"],
                    "reason": "an event before this one was removed or reordered"}
        if _event_hash(e.get("prev_hash", ""), rec) != e["hash"]:
            return {"ok": False, "checked": checked, "legacy": legacy, "event": e["id"],
                    "reason": "this event was changed after it was written"}
        prev, checked = e["hash"], checked + 1
    return {"ok": True, "checked": checked, "legacy": legacy, "head": prev}


def audit_history(limit: int = 2000) -> tuple[list[dict], dict]:
    """The latest `limit` audit events, oldest first, and whether their hash chain is intact."""
    events = _docs("audit", limit)[::-1]
    return [_public(e) for e in events], verify_chain(events)


# --- Requests: refusals become tracked handoffs; access requests wait for approval -------

def save_request(person: str, team: str, title: str, details: str, kind: str = "change", **extra) -> str:
    ref = _col("requests").document()
    ref.set({"ts": now(), "from": person, "team": team, "type": kind, "title": title[:200],
             "details": details[:2000], "status": "open" if kind == "change" else "pending",
             "history": [], **extra})
    return ref.id


def _request_out(r: dict) -> dict:
    status = "open" if r.get("status") == "drafted" else r.get("status")  # drafts from before the inbox
    return {**r, "ts": _iso(r.get("ts")), "updated": _iso(r.get("updated")),
            "type": r.get("type", "change"), "status": status}


def list_requests(limit: int = 200) -> list[dict]:
    return [_request_out(r) for r in _docs("requests", limit)]


def get_request(rid: str) -> dict | None:
    d = _col("requests").document(rid).get()
    return _request_out({**d.to_dict(), "id": d.id}) if d.exists else None


def update_request(rid: str, status: str, by: str, note: str = "", **extra) -> None:
    _col("requests").document(rid).update({
        "status": status, "updated": now(), **extra,
        "history": firestore.ArrayUnion([{"ts": now().isoformat(), "by": by, "status": status,
                                          "note": note[:300]}])})


# --- Members added through onboarding ---------------------------------------------------

def list_members() -> list[dict]:
    return [{**d.to_dict(), "id": d.id} for d in _col("members").stream()]


def save_member(m: dict) -> None:
    _col("members").document(m["id"]).set({**m, "ts": now()})


def update_member(mid: str, **fields) -> None:
    _col("members").document(mid).update({**fields, "updated": now()})


# --- Temporary elevations --------------------------------------------------------------

def save_grant(grant: dict) -> str:
    ref = _col("grants").document()
    ref.set({**grant, "ts": now()})
    return ref.id


def active_grants() -> list[dict]:
    q = _col("grants").where(filter=FieldFilter("status", "==", "active"))
    return [{**d.to_dict(), "id": d.id} for d in q.stream()]


def set_grant_status(gid: str, status: str) -> None:
    _col("grants").document(gid).update({"status": status})


def end_grant(gid: str, status: str, by: str) -> None:
    _col("grants").document(gid).update({"status": status, "ended_by": by, "ended": now()})


# --- Answers (for the impact numbers) ---------------------------------------------------

def log_answer(rec: dict) -> None:
    _col("answers").add({"ts": now(), **rec})


def answers(limit: int = 500) -> list[dict]:
    return [{**a, "ts": _iso(a.get("ts"))} for a in _docs("answers", limit)]


# --- Policy changes made in Govern > Policy (on top of role.yaml) -----------------------

def get_policy() -> dict:
    doc = _col("settings").document("policy").get()
    return doc.to_dict() if doc.exists else {}


def save_policy(o: dict, by: str) -> None:
    _col("settings").document("policy").set({"levels": o.get("levels", {}), "models": o.get("models", {}),
                                             "by": by, "ts": now()})


# --- Repo access changed in Govern > Repo access ------------------------------------------

def get_access() -> dict:
    doc = _col("settings").document("access").get()
    return doc.to_dict() if doc.exists else {}


def save_access(people: dict, by: str) -> None:
    _col("settings").document("access").set({"people": people, "by": by, "ts": now()})


# --- Saved chats ------------------------------------------------------------------------
# One document per chat, owned by a browser (its random session id) and a person, so two
# visitors on the same persona never see each other's chats. Firestore's TTL policy on
# `expires` deletes a chat 30 days after it was last used.

CHAT_DAYS = 30
MAX_TURNS = 40


def _owned(doc, session: str, person: str) -> dict | None:
    c = doc.to_dict() if doc.exists else None
    return c if c and c.get("session") == session and c.get("person") == person else None


def get_chat(cid: str, session: str, person: str) -> dict | None:
    c = _owned(_col("chats").document(cid).get(), session, person)
    if c:
        c["turns"] = [{**t, "r": json.loads(t["r"])} for t in c.get("turns", [])]
    return c


def save_turn(cid: str, session: str, person: str, question: str, result: dict) -> bool:
    """Append a question and its answer. The answer is stored as JSON text: it holds nested
    lists Firestore can't store as fields, and it is only ever read back whole."""
    ref = _col("chats").document(cid)
    doc = ref.get()
    if doc.exists:
        c = _owned(doc, session, person)
        if c is None:
            return False   # someone else's id: never write into another browser's chat
    else:
        c = {"session": session, "person": person, "title": " ".join(question.split())[:80], "created": now()}
    turns = c.get("turns", []) + [{"q": question, "r": json.dumps(result, default=str), "at": now().isoformat()}]
    turns = turns[-MAX_TURNS:]
    while len(turns) > 1 and sum(len(t["q"]) + len(t["r"]) for t in turns) > 700_000:  # 1 MB per document
        turns.pop(0)
    ref.set({**c, "turns": turns, "n": len(turns), "updated": now(), "project": result.get("project"),
             "expires": now() + datetime.timedelta(days=CHAT_DAYS)})
    return True


def list_chats(session: str, person: str, limit: int = 30) -> list[dict]:
    q = (_col("chats").where(filter=FieldFilter("session", "==", session))
         .where(filter=FieldFilter("person", "==", person)).select(["title", "updated", "n", "project"]))
    rows = sorted(({**d.to_dict(), "id": d.id} for d in q.stream()),
                  key=lambda c: c.get("updated") or now(), reverse=True)[:limit]
    return [{"id": c["id"], "title": c.get("title") or "", "updated": _iso(c.get("updated")), "turns": c.get("n") or 0,
             "project": c.get("project")} for c in rows]


def delete_chat(cid: str, session: str, person: str) -> bool:
    ref = _col("chats").document(cid)
    if _owned(ref.get(), session, person) is None:
        return False
    ref.delete()
    return True


# --- GitHub pull requests (fine-grained token for firstround-demo only) -----------------

def _gh(method: str, path: str, **kw) -> dict:
    headers = {"Authorization": f"Bearer {secret('github-token')}",
               "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    try:
        r = httpx.request(method, f"https://api.github.com/repos/{GITHUB_REPO}{path}",
                          headers=headers, timeout=30, **kw)
    except httpx.HTTPError as e:
        raise UpstreamError(f"GitHub didn't answer ({type(e).__name__})") from e
    if r.status_code >= 400:
        raise UpstreamError(f"GitHub {method} {path.split('?')[0]}: {r.status_code} {r.text[:160]}")
    return r.json()


def _gh_read(repo: str, path: str, accept: str, timeout: float) -> httpx.Response:
    """Read from any repository RoleSpace serves (all public). The token raises the rate limit;
    without it the call still works, just with GitHub's anonymous limit."""
    headers = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28"}
    try:
        headers["Authorization"] = f"Bearer {secret('github-token')}"
    except Exception:
        pass
    url = f"https://api.github.com/repos/{repo}{path}"
    try:
        r = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        if r.status_code == 401 and "Authorization" in headers:   # an expired token: public repos still read
            headers.pop("Authorization")
            r = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
    except httpx.HTTPError as e:
        raise UpstreamError(f"GitHub didn't answer ({type(e).__name__})") from e
    if r.status_code >= 400:
        raise UpstreamError(f"GitHub {path.split('?')[0]} for {repo}: {r.status_code} {r.text[:120]}")
    return r


def github_list(repo: str, path: str) -> list:
    return _gh_read(repo, path, "application/vnd.github+json", 15).json()


def github_head(repo: str) -> str:
    """The commit the repository's default branch (main) points to right now."""
    return _gh_read(repo, "/commits/HEAD", "application/vnd.github.sha", 5).text.strip()


def github_tarball(repo: str, sha: str) -> bytes:
    return _gh_read(repo, f"/tarball/{sha}", "application/vnd.github+json", 60).content


def open_pr(branch: str, path: str, old_text: str, new_text: str, title: str, body: str,
            author: tuple[str, str] | None = None) -> str:
    """Branch from main, apply one exact text replacement to one file, open a PR. Returns its URL.

    RoleSpace's GitHub identity opens it, under policy. The person reviewed the change and chose
    to open it, so the commit is theirs: `author` (name, email) is its author and committer."""
    main_sha = _gh("GET", "/git/ref/heads/main")["object"]["sha"]
    current = _gh("GET", f"/contents/{path}", params={"ref": "main"})
    text = base64.b64decode(current["content"]).decode()
    if text.count(old_text) != 1:
        raise UpstreamError(f"{path} changed on GitHub since the preview; ask again for a fresh edit")
    _gh("POST", "/git/refs", json={"ref": f"refs/heads/{branch}", "sha": main_sha})
    who = {"author": {"name": author[0], "email": author[1]},
           "committer": {"name": author[0], "email": author[1]}} if author else {}
    _gh("PUT", f"/contents/{path}", json={
        "message": title, "branch": branch, "sha": current["sha"], **who,
        "content": base64.b64encode(text.replace(old_text, new_text).encode()).decode()})
    return _gh("POST", "/pulls", json={"title": title, "head": branch, "base": "main",
                                        "body": body})["html_url"]


_pr_cache: dict[int, tuple[float, dict]] = {}


def pr_status(number: int) -> dict:
    """Where a pull request stands, as RoleSpace shows it to the person (cached for 30 s)."""
    hit = _pr_cache.get(number)
    if hit and time.time() - hit[0] < 30:
        return hit[1]
    pr = _gh("GET", f"/pulls/{number}")
    checks = _gh("GET", f"/commits/{pr['head']['sha']}/check-runs").get("check_runs", [])
    reviews = _gh("GET", f"/pulls/{number}/reviews")
    review_states = [r["state"] for r in reviews if r.get("state") in ("APPROVED", "CHANGES_REQUESTED")]
    conclusions = [c.get("conclusion") or c.get("status") for c in checks]
    out = {
        "number": number, "url": pr["html_url"], "title": pr["title"],
        "state": "merged" if pr.get("merged") else pr["state"],
        "checks": "failing" if any(c in ("failure", "cancelled", "timed_out") for c in conclusions)
        else "pending" if any(c in ("queued", "in_progress", None) for c in conclusions)
        else "passing" if conclusions else "none",
        "review": review_states[-1].lower().replace("_", " ") if review_states else "waiting for review",
        "comments": pr.get("comments", 0) + pr.get("review_comments", 0),
        "updated": pr.get("updated_at"),
    }
    _pr_cache[number] = (time.time(), out)
    return out
