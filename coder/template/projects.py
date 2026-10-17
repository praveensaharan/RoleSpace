"""The workspace's Projects page: one row per repository, VS Code on one side, Gemini CLI on the other.

Started by the template's startup script and shown in Coder as the "Projects" app. It reads
each repo's branch, last commit and uncommitted changes on every request, so it stays current.
Links are relative to the app's own path-based URL, so they open the workspace's other apps:
    /@owner/workspace.agent/apps/projects/  ->  ../code-<repo>/   and   ../../terminal?command=...

    python3 projects.py PORT REPO [REPO ...]
"""

import html
import http.server
import pathlib
import re
import subprocess
import sys
import urllib.parse

PORT, REPOS = int(sys.argv[1]), sys.argv[2:]
HOME = pathlib.Path.home() / "projects"


def slug(prefix: str, name: str) -> str:
    """The same app slug the template builds: lower-case, runs of other characters to "-", 32 max."""
    return (prefix + re.sub(r"[^A-Za-z0-9]+", "-", name).lower())[:32]


def git(repo: pathlib.Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=5)
    return out.stdout.strip() if out.returncode == 0 else ""


def row(name: str) -> str:
    repo, e = HOME / name, html.escape
    if not (repo / ".git").exists():
        state = '<span class="tag warn">Cloning…</span>'
        branch = commit = remote = ""
    else:
        branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD") or "?"
        commit = git(repo, "log", "-1", "--format=%h · %s · %cr")
        remote = re.sub(r"^https://github.com/|\.git$", "", git(repo, "remote", "get-url", "origin"))
        changed = len([x for x in git(repo, "status", "--porcelain").splitlines() if x])
        state = (f'<span class="tag warn">{changed} uncommitted change{"s" if changed != 1 else ""}</span>' if changed
                 else '<span class="tag ok">Clean</span>')
    folder = f"/home/coder/projects/{name}"
    code = f"../{slug('code-', name)}/?folder={urllib.parse.quote(folder)}"
    gemini = "../../terminal?command=" + urllib.parse.quote(f"cd ~/projects/{name} && gemini")
    shell = "../../terminal?command=" + urllib.parse.quote(f"cd ~/projects/{name} && exec bash -l")
    return f"""<tr>
      <td><div class="repo"><span class="mark">{name[:1].upper()}</span><div><b>{e(name)}</b>
        <small>{e(remote) or "&nbsp;"}</small></div></div></td>
      <td><span class="branch">{e(branch) or "–"}</span><small class="commit">{e(commit)}</small></td>
      <td>{state}</td>
      <td class="act"><a class="btn code" href="{e(code)}" target="_blank" rel="noopener"><i></i>VS Code</a></td>
      <td class="act"><a class="btn gem" href="{e(gemini)}" target="_blank" rel="noopener"><i></i>Gemini CLI</a>
        <a class="btn ghost" href="{e(shell)}" target="_blank" rel="noopener" title="A terminal in this repo">Terminal</a></td></tr>"""


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Projects</title>
<meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="refresh" content="30">
<style>
  :root { --ink: #111; --body: #374151; --muted: #6b7280; --line: #e5e7eb; --soft: #f8f9fa; --ok: #10b981; --warn: #f59e0b; }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--soft); color: var(--body); font: 14px/1.5 Inter, -apple-system, "Segoe UI", Roboto, sans-serif; }
  main { max-width: 1160px; margin: 40px auto; padding: 0 24px; }
  h1 { margin: 0; color: var(--ink); font: 600 26px/1.2 Inter, -apple-system, sans-serif; letter-spacing: -0.5px; }
  p.lead { margin: 6px 0 24px; color: var(--muted); }
  .card { background: #fff; border: 1px solid var(--line); border-radius: 14px; overflow: hidden; box-shadow: 0 1px 2px rgba(0,0,0,.05); }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; font: 500 12px/1 Inter, sans-serif; color: var(--muted); padding: 12px 16px; background: var(--soft);
       border-bottom: 1px solid var(--line); text-transform: uppercase; letter-spacing: .04em; }
  th.side { text-align: center; } td { padding: 14px 14px; border-bottom: 1px solid var(--line); vertical-align: middle; }
  tr:last-child td { border-bottom: 0; } tr:hover td { background: #fcfcfd; }
  .repo { display: flex; gap: 12px; align-items: center; }
  .mark { flex: none; width: 36px; height: 36px; border-radius: 9px; background: #101010; color: #fff; display: grid; place-items: center; font-weight: 600; }
  .repo b { display: block; color: var(--ink); font-size: 15px; white-space: nowrap; } small { display: block; color: var(--muted); font-size: 12px; }
  .repo small, .commit { font-family: "JetBrains Mono", ui-monospace, Menlo, monospace; white-space: nowrap; }
  .commit { max-width: 240px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px; }
  .branch { display: inline-block; padding: 1px 8px; border-radius: 999px; background: #f3f4f6; color: var(--ink);
            font: 500 12px/18px "JetBrains Mono", ui-monospace, monospace; }
  .tag { display: inline-flex; align-items: center; gap: 6px; height: 22px; padding: 0 9px; border-radius: 999px; font-size: 12px; font-weight: 500; white-space: nowrap; }
  .tag::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
  .tag.ok { background: #ecfdf5; color: #047857; } .tag.warn { background: #fffbeb; color: #b45309; }
  .act { text-align: center; white-space: nowrap; }
  .btn { display: inline-flex; align-items: center; gap: 8px; height: 34px; padding: 0 14px; border-radius: 8px; text-decoration: none;
         font: 500 13px/1 Inter, sans-serif; border: 1px solid var(--line); color: var(--ink); background: #fff; transition: .12s; }
  .btn:hover { box-shadow: 0 4px 12px rgba(0,0,0,.08); transform: translateY(-1px); }
  .btn i { width: 16px; height: 16px; border-radius: 4px; }
  .btn.code { background: #111; color: #fff; border-color: #111; } .btn.code i { background: linear-gradient(135deg, #3b82f6, #22d3ee); }
  .btn.gem { background: #fff; } .btn.gem i { background: conic-gradient(from 200deg, #4285f4, #9b72cb, #d96570, #4285f4); border-radius: 50%; }
  .btn.ghost { border-color: transparent; color: var(--muted); padding: 0 10px; } .btn.ghost:hover { color: var(--ink); box-shadow: none; }
  footer { margin-top: 14px; color: var(--muted); font-size: 12px; display: flex; gap: 16px; flex-wrap: wrap; }
  footer a { color: var(--muted); }
</style></head><body><main>
  <h1>Projects</h1>
  <p class="lead">Every repository you have access to, cloned in <code>~/projects</code>. Pick one and open it in VS Code or
    Gemini CLI. Gemini CLI uses your own gateway key and budget.</p>
  <div class="card"><table><thead><tr><th>Repository</th><th>Branch · last commit</th><th>Status</th>
    <th class="side">VS Code</th><th class="side">Gemini CLI</th></tr></thead><tbody>__ROWS__</tbody></table></div>
  <footer><span>Updates every 30 s.</span><a href="__ALL__" target="_blank" rel="noopener">Open all repos in one VS Code window</a></footer>
</main></body></html>"""


class Page(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = PAGE.replace("__ROWS__", "".join(row(r) for r in REPOS)).replace(
            "__ALL__", "../code-server/?folder=" + urllib.parse.quote("/home/coder/projects")).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Page).serve_forever()
