"""Relay from workspaces to the model gateway, adding this VM's Google identity.

The gateway on Cloud Run takes two things: a Google identity with run.invoker (this
VM's service account has it, and nothing else), and the person's own LiteLLM key,
which Gemini CLI sends itself. Workspaces reach this relay at host.docker.internal:4000.
Only IAP can reach this VM (ports 22 and 3000), so 4000 is not reachable from outside.

Gemini CLI asks for Google's own model IDs (its Auto mode picks them itself, e.g.
gemini-3.8-flash or gemini-3.1-pro-preview), while the gateway serves stable names that each
person's key lists. The relay maps one to the other in the URL; the key still decides, so a
level without a Pro model still gets a 403 for a Pro request.

Only model calls pass: Gemini's API (/v1beta/models/...) and OpenAI-style chat. Admin routes,
the LiteLLM UI and everything else get a 403 here, before they reach the gateway.
"""

import http.client
import http.server
import os
import re
import threading
import time
import urllib.parse
import urllib.request

GATEWAY = os.environ["GATEWAY_URL"]
HOST = urllib.parse.urlsplit(GATEWAY).hostname
METADATA = ("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/"
            "default/identity?audience=" + urllib.parse.quote(GATEWAY, safe=""))
SKIP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
        "transfer-encoding", "upgrade", "host", "content-length", "date", "server"}

GATEWAY_MODELS = {"gemini-flash", "gemini-pro"}
MODEL_IN_PATH = re.compile(r"(/models/)([^/:?]+)")
ALLOWED = re.compile(r"^/(v1beta|v1)/models(/[^/?]+)?([:?].*)?$|^/(v1/)?chat/completions(\?.*)?$")

_token, _expires, _lock = "", 0.0, threading.Lock()


def gateway_model(name: str) -> str:
    """Google's model ID -> the gateway's name for it (anything else passes through)."""
    if name in GATEWAY_MODELS or not name.startswith("gemini-") or "embedding" in name:
        return name
    return "gemini-pro" if "-pro" in name else "gemini-flash"


def gateway_path(path: str) -> str:
    return MODEL_IN_PATH.sub(lambda m: m.group(1) + gateway_model(m.group(2)), path, count=1)


def id_token() -> str:
    global _token, _expires
    with _lock:
        if time.time() > _expires:  # Google ID tokens last an hour
            req = urllib.request.Request(METADATA, headers={"Metadata-Flavor": "Google"})
            _token = urllib.request.urlopen(req, timeout=10).read().decode()
            _expires = time.time() + 45 * 60
        return _token


class Relay(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def relay(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if not ALLOWED.match(self.path) or ".." in self.path or "%2" in self.path.lower() or "%5c" in self.path.lower():
            msg = b'{"error": {"message": "Only model calls go through this relay", "code": 403}}'
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
            return
        headers = {k: v for k, v in self.headers.items() if k.lower() not in SKIP}
        headers["X-Serverless-Authorization"] = "Bearer " + id_token()
        upstream = http.client.HTTPSConnection(HOST, timeout=600)
        upstream.request(self.command, gateway_path(self.path), body=body or None, headers=headers)
        resp = upstream.getresponse()
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() not in SKIP:
                self.send_header(k, v)
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        while chunk := resp.read1(65536):  # stream, so Gemini CLI's SSE answers arrive live
            self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
            self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")
        upstream.close()

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = relay

    def log_message(self, *args) -> None:
        pass  # the gateway keeps the log, per person


http.server.ThreadingHTTPServer(("0.0.0.0", int(os.getenv("PORT", "4000"))), Relay).serve_forever()
