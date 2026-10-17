"""Temporary access: just-in-time elevation that ends by itself.

A Govern-level person approves a request; for the approved hours the person works at the
higher level (agent tools and paths from role.yaml) and their gateway key carries that level's
models. When the time is up, or an admin ends it early, both change back and the audit log
records it. Grants live in Firestore and in memory (one app instance).
"""

import threading
import time

import roles
import services

_lock = threading.Lock()
_grants: dict[str, dict] = {}  # person id -> active grant
_loaded = {"at": 0.0}


def _load() -> None:
    if _loaded["at"]:
        return
    for g in services.active_grants():
        _grants[g["person"]] = g
    _loaded["at"] = time.time()


def active(pid: str) -> dict | None:
    """The person's grant if it is still running; ends it on the spot if its time is up."""
    with _lock:
        _load()
        g = _grants.get(pid)
    if g and g["expires_at"] <= time.time():
        try:
            end(pid, "system", "expired")
        except services.UpstreamError:
            pass  # the app already treats it as ended; the key change is retried next time
        return None
    return g


def effective(pid: str) -> dict:
    """The person as RoleSpace treats them right now: their level, or their elevated level."""
    g = active(pid)
    p = roles.person(pid, g["level"] if g else None)
    return {**p, "grant": _public(g) if g else None}


def _public(g: dict) -> dict:
    return {k: g[k] for k in ("id", "level", "from_level", "expires_at", "approved_by", "reason", "request_id") if k in g}


def grant(pid: str, level: str, hours: float, approved_by: str, reason: str, request_id: str) -> dict:
    base = roles.person(pid)
    if level not in roles.elevation_targets(base["level"]):
        raise ValueError(f"role.yaml doesn't allow {base['level']} to be elevated to {level}")
    hours = max(0.25, min(roles.elevation_max_hours(), float(hours)))
    if active(pid):
        raise ValueError(f"{base['name']} already has a temporary level")
    models = roles.config()["levels"][level]["models"]
    g = {"person": pid, "level": level, "from_level": base["level"], "expires_at": time.time() + hours * 3600,
         "approved_by": approved_by, "reason": reason[:300], "request_id": request_id, "status": "starting"}
    g["id"] = services.save_grant(g)  # recorded first, so a key change never exists without a record
    try:
        services.key_update(pid, models=sorted(set(models) | set(base["level_cfg"]["models"])))
    except services.UpstreamError:
        services.set_grant_status(g["id"], "failed")
        raise
    services.set_grant_status(g["id"], "active")
    g["status"] = "active"
    with _lock:
        _grants[pid] = g
    services.audit("elevation_granted", approved_by, "govern",
                   f"{base['name']} raised from {base['level']} to {level} for {hours:g} h: {reason[:120]}",
                   target=pid, until=time.strftime("%H:%M UTC", time.gmtime(g["expires_at"])))
    return _public(g)


def end(pid: str, by: str, how: str = "revoked") -> bool:
    """Put the person back on their own level. how: expired | revoked."""
    with _lock:
        g = _grants.pop(pid, None)
    if not g:
        return False
    base = roles.person(pid)
    try:
        services.key_update(pid, models=base["level_cfg"]["models"])
    except services.UpstreamError:
        with _lock:  # keep the grant so the next check retries the key change
            _grants[pid] = g
        raise
    services.end_grant(g["id"], how, by)
    if g.get("request_id"):
        services.update_request(g["request_id"], "expired" if how == "expired" else "revoked", by)
    services.audit("elevation_ended", by, "govern" if by != "system" else "system",
                   f"{base['name']} back to {base['level']} ({how})", target=pid)
    return True


def all_active() -> list[dict]:
    """Every running grant (ending any that have run out)."""
    with _lock:
        _load()
        pids = list(_grants)
    return [{"person": pid, **_public(g)} for pid in pids if (g := active(pid))]
