"""Relay from workspaces to the model gateway, adding this VM's Google identity.

The gateway on Cloud Run takes two things: a Google identity with run.invoker (this
VM's service account has it, and nothing else), and the person's own LiteLLM key,
which Gemini CLI sends itself. Workspaces reach this relay at host.docker.internal:4000.
Only IAP can reach this VM (ports 22 and 3000), so 4000 is not reachable from outside.
"""

import http.client
import http.server
import os
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

_token, _expires, _lock = "", 0.0, threading.Lock()


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
        headers = {k: v for k, v in self.headers.items() if k.lower() not in SKIP}
        headers["X-Serverless-Authorization"] = "Bearer " + id_token()
        upstream = http.client.HTTPSConnection(HOST, timeout=600)
        upstream.request(self.command, self.path, body=body or None, headers=headers)
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
