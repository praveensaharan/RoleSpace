"""RoleSpace public website: the static site plus one lookup, work email -> organization.

The lookup only ever returns workspaces listed in orgs.json, so it can't be turned into an open
redirect. Everything is served with a strict Content-Security-Policy (no inline script or style).
"""

import collections
import ipaddress
import json
import os
import re
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

HERE = Path(__file__).parent
STATIC = HERE / "static"
CONFIG = json.loads((HERE / "orgs.json").read_text())
ORGS, PERSONAL = CONFIG["orgs"], set(CONFIG["personal_domains"])
DEMO = ORGS[CONFIG["demo"]]
EMAIL = re.compile(r"^[a-z0-9._%+-]{1,64}@([a-z0-9-]{1,63}\.)+[a-z]{2,24}$")
LOOKUPS_PER_MINUTE = 20
_seen: dict[str, collections.deque] = collections.defaultdict(collections.deque)

CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'")

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(GZipMiddleware, minimum_size=800)


@app.middleware("http")
async def headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.update({
        "Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin", "Strict-Transport-Security": "max-age=31536000",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()",
        "Cross-Origin-Opener-Policy": "same-origin"})
    if request.url.path.startswith("/assets/"):
        resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


class Lookup(BaseModel):
    email: str = Field(max_length=200)


# Proxies whose hops we skip in X-Forwarded-For: Google's front ends, plus our load balancer's IP
# (set TRUSTED_PROXIES at deploy). Reading from the right, the first other address is the caller;
# anything a client writes on the left can't change that.
TRUSTED = [ipaddress.ip_network(n.strip()) for n in
           os.getenv("TRUSTED_PROXIES", "35.191.0.0/16,130.211.0.0/22").split(",") if n.strip()]


def _client(request: Request) -> str:
    hops = [h.strip() for h in (request.headers.get("x-forwarded-for") or "").split(",") if h.strip()]
    for hop in reversed(hops):
        try:
            ip = ipaddress.ip_address(hop)
        except ValueError:
            continue
        if not any(ip in net for net in TRUSTED):
            return hop
    return request.client.host if request.client else "?"


@app.post("/api/org")
def org(body: Lookup, request: Request) -> JSONResponse:
    """Which workspace a work email belongs to. Personal and unknown domains get the demo workspace."""
    now, ip = time.time(), _client(request)
    if len(_seen) > 5000:   # drop callers idle for a minute, so the table can't grow without bound
        for k in [k for k, d in _seen.items() if not d or now - d[-1] > 60]:
            del _seen[k]
    q = _seen[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= LOOKUPS_PER_MINUTE:
        raise HTTPException(429, "Too many lookups. Try again in a minute.")
    q.append(now)
    email = body.email.strip().lower()
    if not EMAIL.match(email):
        raise HTTPException(400, "Enter a full email address, like name@company.com.")
    domain = email.split("@", 1)[1]
    if domain in ORGS:
        o = ORGS[domain]
        return JSONResponse({"status": "found", "org": o["name"], "workspace": o["workspace"], "sign_in": o["sign_in"]})
    status = "personal" if domain in PERSONAL else "unknown"
    return JSONResponse({"status": status, "domain": domain, "org": DEMO["name"], "workspace": DEMO["workspace"],
                         "sign_in": DEMO["sign_in"]})


@app.get("/health")
def health() -> dict:
    return {"ok": True}


app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


@app.api_route("/", methods=["GET", "HEAD"])
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/favicon.svg")
def favicon() -> FileResponse:
    return FileResponse(STATIC / "favicon.svg")
