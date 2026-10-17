"""RoleSpace diagrams in the visual language of our earlier design sketch: grey service
containers with an icon tile, slate-blue component boxes, cascaded workspace cards, purple
numbered steps and a red primary path. Content is RoleSpace on Google Cloud, as built.

Writes flow-*.html and renders flow-*.png (2x) with Playwright, next to this script:
    python build_flow_diagrams.py
"""

import html
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
IMG = HERE  # flow-*.html and flow-*.png are written next to this script

FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"
GREY, GREY_LINE, LIGHT_GREY = "#7F7F7F", "#6B6B6B", "#D9D9D9"
SLATE, SLATE_LINE = "#2F5A7E", "#1E3D57"
BLUE, BAND, BAND_LINE = "#4DA9E6", "#DCEBF7", "#5B9BD5"
CARD, CARD_LINE = "#DCE6F2", "#E8822E"
PURPLE, RED, INK = "#7E2F92", "#E0302A", "#111111"
GREEN, GREEN_LINE = "#D5E8D4", "#6AA84F"
LAVENDER = "#EBD8F0"
ICON = {"compute": "#E8822E", "run": "#4285F4", "ai": "#2E9E83", "sql": "#4285F4", "store": "#F29900",
        "secret": "#5F6368", "iap": "#4285F4", "git": "#24292F"}

e = html.escape


# ---- primitives --------------------------------------------------------------------------

def text(x, y, s, size=18, fill=INK, weight=400, anchor="middle", lines=None):
    rows = lines or [s]
    out = []
    for i, row in enumerate(rows):
        out.append(f'<text x="{x}" y="{y + i * size * 1.18:.1f}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
                   f'text-anchor="{anchor}" font-family="{FONT}">{e(row)}</text>')
    return "".join(out)


def box(x, y, w, h, fill, stroke="none", rx=8, sw=1.5, dash=False, shadow=False):
    s = f' stroke-dasharray="7,5"' if dash else ""
    f = ' filter="url(#shadow)"' if shadow else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{s}{f}/>'


def slate(x, y, w, h, label, size=17, lines=None, fill=SLATE):
    n = len(lines or [label])
    ty = y + h / 2 + size * 0.36 - (n - 1) * size * 0.59
    return box(x, y, w, h, fill, SLATE_LINE, rx=7, sw=2) + text(x + w / 2, ty, label, size, "#FFFFFF", lines=lines)


def container(x, y, w, h, title, sub="", icon=None, fill=GREY, title_fill="#FFFFFF"):
    out = [box(x, y, w, h, fill, "none", rx=4, shadow=True)]
    tx = x + w / 2 + (30 if icon else 0)
    out.append(text(tx, y + 38, title, 24, title_fill, 500))
    if sub:
        out.append(text(tx, y + 62, sub, 15, "#EDEDED" if fill == GREY else "#444"))
    if icon:
        out.append(icon_tile(x - 8, y - 8, icon))
    return "".join(out)


def icon_tile(x, y, kind, size=62):
    c = ICON[kind]
    g = [f'<rect x="{x}" y="{y}" width="{size}" height="{size}" fill="{c}"/>']
    cx, cy, s = x + size / 2, y + size / 2, size / 62
    W = 'fill="none" stroke="#FFFFFF" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"'
    if kind == "compute":   # a chip
        g.append(f'<rect x="{cx - 14 * s}" y="{cy - 14 * s}" width="{28 * s}" height="{28 * s}" rx="3" {W}/>')
        g.append(f'<rect x="{cx - 7 * s}" y="{cy - 7 * s}" width="{14 * s}" height="{14 * s}" {W}/>')
        for d in (-8, 0, 8):
            g.append(f'<path d="M{cx + d * s},{cy - 14 * s} v{-6 * s} M{cx + d * s},{cy + 14 * s} v{6 * s} '
                     f'M{cx - 14 * s},{cy + d * s} h{-6 * s} M{cx + 14 * s},{cy + d * s} h{6 * s}" {W}/>')
    elif kind == "run":     # Cloud Run: two chevrons
        g.append(f'<path d="M{cx - 15 * s},{cy - 13 * s} l{12 * s},{13 * s} l{-12 * s},{13 * s} M{cx},{cy - 13 * s} '
                 f'l{12 * s},{13 * s} l{-12 * s},{13 * s}" {W}/>')
    elif kind == "ai":      # Gemini: a four-point spark
        g.append(f'<path d="M{cx},{cy - 18 * s} C{cx + 2 * s},{cy - 4 * s} {cx + 4 * s},{cy - 2 * s} {cx + 18 * s},{cy} '
                 f'C{cx + 4 * s},{cy + 2 * s} {cx + 2 * s},{cy + 4 * s} {cx},{cy + 18 * s} C{cx - 2 * s},{cy + 4 * s} '
                 f'{cx - 4 * s},{cy + 2 * s} {cx - 18 * s},{cy} C{cx - 4 * s},{cy - 2 * s} {cx - 2 * s},{cy - 4 * s} '
                 f'{cx},{cy - 18 * s}Z" fill="#FFFFFF"/>')
    elif kind == "sql":     # a database cylinder
        g.append(f'<ellipse cx="{cx}" cy="{cy - 11 * s}" rx="{14 * s}" ry="{5 * s}" {W}/>')
        g.append(f'<path d="M{cx - 14 * s},{cy - 11 * s} v{22 * s} a{14 * s},{5 * s} 0 0 0 {28 * s},0 v{-22 * s} '
                 f'M{cx - 14 * s},{cy} a{14 * s},{5 * s} 0 0 0 {28 * s},0" {W}/>')
    elif kind == "store":   # documents
        g.append(f'<rect x="{cx - 11 * s}" y="{cy - 15 * s}" width="{22 * s}" height="{28 * s}" rx="2" {W}/>')
        g.append(f'<path d="M{cx - 5 * s},{cy - 6 * s} h{10 * s} M{cx - 5 * s},{cy} h{10 * s} M{cx - 5 * s},{cy + 6 * s} h{6 * s}" {W}/>')
    elif kind == "secret":  # a key
        g.append(f'<circle cx="{cx - 7 * s}" cy="{cy}" r="{7 * s}" {W}/>')
        g.append(f'<path d="M{cx},{cy} h{16 * s} M{cx + 11 * s},{cy} v{6 * s} M{cx + 16 * s},{cy} v{6 * s}" {W}/>')
    elif kind == "iap":     # a shield with a check
        g.append(f'<path d="M{cx},{cy - 17 * s} l{14 * s},{5 * s} v{9 * s} c0,{9 * s} {-6 * s},{15 * s} {-14 * s},{19 * s} '
                 f'c{-8 * s},{-4 * s} {-14 * s},{-10 * s} {-14 * s},{-19 * s} v{-9 * s}Z" {W}/>')
        g.append(f'<path d="M{cx - 6 * s},{cy + 1 * s} l{4 * s},{4 * s} l{8 * s},{-8 * s}" {W}/>')
    elif kind == "git":     # a branch
        g.append(f'<circle cx="{cx - 8 * s}" cy="{cy - 12 * s}" r="{4 * s}" {W}/><circle cx="{cx - 8 * s}" cy="{cy + 12 * s}" r="{4 * s}" {W}/>')
        g.append(f'<circle cx="{cx + 9 * s}" cy="{cy - 6 * s}" r="{4 * s}" {W}/>')
        g.append(f'<path d="M{cx - 8 * s},{cy - 8 * s} v{16 * s} M{cx + 9 * s},{cy - 2 * s} c0,{8 * s} {-17 * s},{6 * s} {-17 * s},{12 * s}" {W}/>')
    return "".join(g)


def step(x, y, n, r=24):
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{PURPLE}" filter="url(#shadow)"/>'
            f'<circle cx="{x - r * 0.25}" cy="{y - r * 0.3}" r="{r * 0.55}" fill="#FFFFFF" opacity="0.10"/>'
            + text(x, y + r * 0.42, str(n), r * 1.25, "#FFFFFF", 500))


def path(d, color=INK, width=2.4, arrow=True, dash=False):
    m = f' marker-end="url(#arrow-{"red" if color == RED else "ink"})"' if arrow else ""
    s = ' stroke-dasharray="8,6"' if dash else ""
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"{s}{m}/>'


def label(x, y, s, size=16, fill=INK, bg="#FFFFFF"):
    w = len(s) * size * 0.56 + 12
    return (f'<rect x="{x - w / 2:.1f}" y="{y - size * 0.95:.1f}" width="{w:.1f}" height="{size * 1.35:.1f}" fill="{bg}"/>'
            + text(x, y, s, size, fill))


def person(x, y, s=1.0, badge=None):
    out = [f'<circle cx="{x}" cy="{y}" r="{20 * s}" fill="{INK}"/>',
           f'<path d="M{x - 38 * s},{y + 62 * s} q0,{-34 * s} {38 * s},{-36 * s} q{38 * s},{2 * s} {38 * s},{36 * s}Z" fill="{INK}"/>']
    if badge:
        out.append(icon_tile(x + 22 * s, y - 8 * s, badge, 34 * s))
    return "".join(out)


def stack(x, y, w, h, n=4, d=24, title="Workspace", items=()):
    out = []
    for i in range(n):
        ox = x + i * d
        oy = y + i * d * 0.95
        out.append(box(ox, oy, w, h, CARD, CARD_LINE, rx=18, sw=2))
    fx, fy = x + (n - 1) * d, y + (n - 1) * d * 0.95
    out.append(text(fx + w / 2, fy + 40, title, 22, INK, 500))
    for i, it in enumerate(items):
        out.append(slate(fx + 26, fy + 58 + i * 52, w - 52, 42, it, 17))
    return "".join(out), (fx, fy)


def page(name, w, h, body):
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <defs>
    <filter id="shadow" x="-10%" y="-10%" width="130%" height="130%"><feDropShadow dx="2" dy="3" stdDeviation="2.5" flood-opacity="0.22"/></filter>
    <marker id="arrow-ink" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8Z" fill="{INK}"/></marker>
    <marker id="arrow-red" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8Z" fill="{RED}"/></marker>
  </defs>
  <rect width="{w}" height="{h}" fill="#FFFFFF"/>
  {body}
</svg>"""
    (IMG / f"{name}.html").write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0}}</style>'
                                      f'</head><body>{svg}</body></html>')
    return name


# ---- 1. Environment usage flow ---------------------------------------------------------------

def env_flow():
    W, H = 1500, 905
    b = []
    people = [("Maya", "PM · Ask"), ("Leo", "Designer · Suggest"), ("Sam", "Developer · Build"), ("Ava", "Admin · Govern")]
    for i, (n, r) in enumerate(people):
        x = 180 + i * 250
        b.append(person(x, 46, 0.72))
        b.append(text(x, 128, n, 19, INK, 600))
        b.append(text(x, 150, r, 15, "#555"))
        b.append(path(f"M{x},{158} V{196}"))
    # 1 sign-in bar
    b.append(box(60, 196, 1000, 52, "#FFFFFF", INK, rx=4, sw=2))
    b.append(text(560, 230, "Google sign-in · Identity-Aware Proxy (no VPN)", 21, INK, 500))
    b.append(step(1085, 222, 1))
    # 2 app band and 3 workspace band
    b.append(box(40, 290, 600, 210, BAND, BAND_LINE, rx=4, sw=2))
    b.append(text(340, 328, "RoleSpace app · Cloud Run", 23, INK, 500))
    for i, (t, sub) in enumerate([("Ask agent", "answers + citations"), ("Suggest agent", "edits as PRs"), ("Govern", "people · spend · audit")]):
        x = 62 + i * 192
        b.append(box(x, 350, 176, 118, "#FFFFFF", GREY_LINE, rx=4))
        b.append(text(x + 88, 400, t, 19, INK, 600))
        b.append(text(x + 88, 428, sub, 14, "#555"))
    b.append(step(640, 290, 2))
    b.append(box(680, 290, 380, 210, BAND, BAND_LINE, rx=4, sw=2))
    b.append(text(870, 328, "Coder workspaces · private VM", 23, INK, 500))
    for i, t in enumerate(["Workspace 1", "Workspace 2", "Workspace n"]):
        x = 700 + i * 118
        b.append(box(x, 350, 106, 118, "#FFFFFF", GREY_LINE, rx=4))
        b.append(text(x + 53, 400, t.split()[0], 17, INK, 600))
        b.append(text(x + 53, 424, t.split()[1], 17, INK, 600))
    b.append(step(1060, 290, 3))
    for x in (180, 430, 680):
        b.append(path(f"M{x},{248} V{290}"))
    b.append(path(f"M930,248 V290"))
    # 4 gateway band
    b.append(box(40, 560, 1020, 170, BAND, BAND_LINE, rx=4, sw=2))
    b.append(text(550, 598, "Model gateway · LiteLLM on Cloud Run", 23, INK, 500))
    b.append(box(90, 618, 920, 82, LIGHT_GREY, GREY_LINE, rx=4, sw=1.5))
    b.append(text(550, 652, "One key per person: allowed models, monthly budget, kill switch", 19, INK, 500))
    b.append(text(550, 680, "every call logged with its cost; keys reach model routes only", 16, "#444"))
    b.append(step(1060, 560, 4))
    b.append(path("M340,500 V560", RED, 3))
    b.append(path("M870,500 V560", RED, 3))
    b.append(label(300, 546, "own key", 15, RED))
    b.append(label(830, 546, "own key", 15, RED))
    # 5 Gemini
    b.append(box(380, 800, 340, 92, GREEN, GREEN_LINE, rx=4, sw=2))
    b.append(text(550, 840, "Gemini on Vertex AI", 23, INK, 600))
    b.append(text(550, 868, "Flash · Pro", 17, "#444"))
    b.append(path("M550,730 V800", RED, 3.2))
    b.append(label(550, 772, "only path to Gemini", 15, RED))
    b.append(step(720, 800, 5))
    # right side: policy, repo, records
    b.append(box(1150, 196, 300, 120, "#FFFFFF", INK, rx=4, sw=2))
    b.append(text(1300, 238, "role.yaml policy", 21, INK, 600))
    b.append(text(1300, 266, "decides every level, tool,", 16, "#444"))
    b.append(text(1300, 288, "path, model and budget", 16, "#444"))
    b.append(box(1150, 380, 300, 120, "#FFFFFF", INK, rx=4, sw=2))
    b.append(text(1300, 422, "Source code repository", 20, INK, 600))
    b.append(text(1300, 450, "GitHub · CI check", 16, "#444"))
    b.append(text(1300, 472, "one human review", 16, "#444"))
    b.append(path("M1150,420 H1060", INK, 2))
    b.append(label(1105, 412, "clone", 14))
    b.append(path("M430,468 V522 H1120 V480 H1150", RED, 2.6))
    b.append(label(980, 522, "pull request", 15, RED))
    b.append(step(1450, 380, 6))
    b.append(box(1150, 600, 300, 120, "#FFFFFF", INK, rx=4, sw=2))
    b.append(text(1300, 642, "Audit log and spend", 20, INK, 600))
    b.append(text(1300, 670, "Firestore (hash-chained)", 16, "#444"))
    b.append(text(1300, 692, "Cloud SQL (keys, spend)", 16, "#444"))
    b.append(path("M1060,660 H1150", INK, 2))
    return page("flow-1-env-usage", W, H, "".join(b))


# ---- 2. From a laptop to a pull request ----------------------------------------------------

def work_flow():
    W, H = 1720, 1120
    b = []
    # the laptop: a browser, nothing installed
    b.append(box(150, 100, 520, 470, LIGHT_GREY, "#BFBFBF", rx=4, sw=3))
    b.append('<path d="M150,570 L670,570 L720,620 L100,620 Z" fill="#E7E7E7" stroke="#BFBFBF" stroke-width="3"/>')
    b.append(person(52, 300, 1.0, "iap"))
    b.append(path("M112,325 H150", INK, 2.2))
    b.append(box(182, 130, 456, 170, BLUE, "none", rx=26))
    b.append(text(410, 170, "Browser only", 24, "#FFFFFF", 500))
    b.append(slate(232, 190, 356, 44, "RoleSpace app", 19))
    b.append(slate(232, 242, 356, 44, "VS Code in the browser", 19))
    b.append(box(172, 316, 476, 142, "none", RED, rx=2, sw=3.5))
    b.append(slate(232, 328, 356, 52, "Assistant: Ask · Suggest", 19, fill="#5B9BD5"))
    b.append(slate(232, 392, 356, 52, "Gemini CLI in the terminal", 19, fill="#5B9BD5"))
    b.append(box(182, 476, 456, 74, "#5B9BD5", SLATE_LINE, rx=4, sw=2))
    b.append(text(410, 508, "No code and no keys on the laptop", 19, "#FFFFFF", 500))
    b.append(text(410, 532, "everything runs in Google Cloud", 16, "#EAF2FB"))
    # the app, under the laptop
    b.append(container(150, 760, 520, 230, "Cloud Run · RoleSpace app", "", "run"))
    b.append(slate(190, 820, 210, 50, "Ask agent", 19))
    b.append(slate(420, 820, 210, 50, "Suggest agent", 19))
    b.append(slate(190, 890, 440, 50, "Govern: people · spend · audit", 18))
    b.append(path("M410,620 V760", RED, 3))
    b.append(label(540, 712, "Google sign-in · IAP", 16, RED))
    b.append(step(410, 670, 1, 28))
    # Coder VM with the workspace stack
    b.append(container(800, 70, 560, 520, "Compute Engine · coder-vm", "private subnet, no public IP", "compute"))
    st, (fx, fy) = stack(850, 120, 360, 330, 4, 22, "Workspace (Sam)",
                         ["VS Code server", "Gemini CLI", "Terminal", "Repo clone"])
    b.append(st)
    b.append(path(f"M638,264 H730 V{fy + 79} H{fx + 26}"))
    b.append(label(735, 236, "IAP tunnel :3000", 15))
    b.append(path(f"M648,418 H760 V{fy + 131} H{fx + 26}", RED, 3))
    b.append(step(760, 330, 2, 28))
    # gateway and Gemini
    b.append(container(800, 700, 560, 150, "Model gateway", "", "run"))
    b.append(box(980, 770, 330, 52, "#DCE6F2", CARD_LINE, rx=6, sw=2))
    b.append(text(1145, 803, "LiteLLM · one key per person", 18, INK, 500))
    b.append(container(800, 900, 560, 130, "Vertex AI", "", "ai"))
    b.append(box(1000, 960, 310, 52, "#DCE6F2", CARD_LINE, rx=6, sw=2))
    b.append(text(1155, 993, "Gemini Flash · Pro", 18, INK, 500))
    b.append(path("M670,796 H980", RED, 3))
    b.append(label(735, 788, "own key", 15, RED))
    b.append(path("M1270,513 V770", RED, 3))
    b.append(label(1270, 650, "own key", 15, RED))
    b.append(step(1200, 650, 3, 28))
    b.append(path("M1280,822 V960", INK, 3))
    b.append(label(1280, 885, "only path", 15))
    # GitHub
    b.append(container(1440, 70, 260, 520, "GitHub", "firstround-demo", "git"))
    b.append(slate(1462, 170, 216, 120, "", 18, lines=["Pull", "requests"]))
    b.append(slate(1462, 310, 216, 120, "", 18, lines=["CI allow-list", "check"]))
    b.append(slate(1462, 450, 216, 110, "", 18, lines=["One human", "review"]))
    b.append(path(f"M{fx + 360},{fy + 58 + 3 * 52 + 21} H1420 V250 H1462"))
    b.append(label(1395, 400, "git push", 15))
    b.append(path("M525,990 V1080 H1570 V590", RED, 3))
    b.append(label(1100, 1080, "Suggest: pull request", 16, RED))
    b.append(step(1570, 860, 4, 28))
    return page("flow-2-work", W, H, "".join(b))


# ---- 3. Project architecture -----------------------------------------------------------------

def project_arch():
    W, H = 1720, 1000
    b = []
    b.append(box(260, 40, 1130, 900, "#FFFFFF", INK, rx=2, sw=2))
    b.append(text(285, 74, "Google Cloud project · us-central1", 20, INK, 600, "start"))
    # serverless band
    b.append(box(300, 100, 700, 220, "#F3F3F3", "#9E9E9E", rx=6, sw=1.5))
    b.append(text(320, 130, "Serverless · Cloud Run", 18, "#333", 600, "start"))
    b.append(container(330, 150, 290, 150, "RoleSpace app", "", "run"))
    b.append(slate(350, 205, 250, 38, "Ask · Suggest agents", 16))
    b.append(slate(350, 251, 250, 38, "Govern screens", 16))
    b.append(container(690, 150, 290, 150, "Model gateway", "", "run"))
    b.append(slate(710, 205, 250, 38, "LiteLLM · per-person keys", 16))
    b.append(slate(710, 251, 250, 38, "budgets · kill switch", 16))
    b.append(path("M620,224 H690", RED, 3))
    b.append(label(655, 216, "own key", 14, RED))
    # managed services column
    b.append(box(1030, 100, 330, 600, "#F3F3F3", "#9E9E9E", rx=6, sw=1.5))
    b.append(text(1050, 130, "Managed services", 18, "#333", 600, "start"))
    svc = [("ai", "Vertex AI", "Gemini Flash · Pro"), ("sql", "Cloud SQL", "keys · budgets · spend"),
           ("store", "Firestore", "audit chain · requests"), ("secret", "Secret Manager", "keys · tokens"),
           ("iap", "Cloud Logging", "every call and decision")]
    for i, (k, t, sub) in enumerate(svc):
        y = 150 + i * 108
        b.append(box(1050, y, 290, 92, "#FFFFFF", "#9E9E9E", rx=4, sw=1.5))
        b.append(icon_tile(1062, y + 22, k, 48))
        b.append(text(1205, y + 40, t, 18, INK, 600))
        b.append(text(1205, y + 66, sub, 15, "#555"))
    b.append(path("M980,190 H1015 V196 H1050", INK, 2.6))
    b.append(path("M980,270 H1015 V304 H1050", INK, 2))
    b.append(text(1190, 768, "Only the gateway's identity has", 16, RED, 600))
    b.append(text(1190, 790, "the Vertex AI role: the app and", 16, RED, 600))
    b.append(text(1190, 812, "the VM get 403 if they try", 16, RED, 600))
    b.append(path("M475,300 V336 H1022 V412 H1050", INK, 1.6, dash=True))
    b.append(label(700, 336, "audit · secrets", 14))
    # VPC
    b.append(box(300, 370, 700, 330, "#FFFFFF", "#8E6CC8", rx=4, sw=2.5, dash=True))
    b.append(text(320, 402, "VPC rs-vpc", 18, "#5E3BA8", 600, "start"))
    b.append(box(320, 420, 660, 260, "#EEF6EA", "#6AA84F", rx=4, sw=2))
    b.append(text(340, 450, "Private subnet rs-private · 10.1.2.0/24", 16, "#2E6B1F", 600, "start"))
    b.append(container(560, 480, 400, 180, "coder-vm", "no public IP", "compute"))
    b.append(box(585, 572, 350, 70, "#DCE6F2", CARD_LINE, rx=6, sw=2))
    b.append(text(760, 600, "Coder · workspaces", 17, INK, 500))
    b.append(text(760, 624, "relay adds the VM's identity", 15, "#444"))
    b.append(box(340, 480, 190, 84, "#FFFFFF", "#9E9E9E", rx=4, sw=1.5))
    b.append(text(435, 512, "Firewall", 17, INK, 600))
    b.append(text(435, 536, "IAP range only, 22 · 3000", 13, "#444"))
    b.append(box(340, 580, 190, 84, "#FFFFFF", "#9E9E9E", rx=4, sw=1.5))
    b.append(text(435, 612, "Cloud NAT", 17, INK, 600))
    b.append(text(435, 636, "outbound only", 14, "#444"))
    b.append(path("M860,480 V300", RED, 3))
    b.append(label(860, 400, "own key", 14, RED))
    # designed, not built
    b.append(box(300, 750, 700, 150, "#FFFFFF", INK, rx=2, sw=1.5, dash=True))
    b.append(text(650, 790, "Designed, not built", 18, "#555", 600))
    b.append(text(650, 822, "Entra ID / Okta groups (SAML, SCIM) · Model Armor", 16, "#555"))
    b.append(text(650, 848, "Cloud KMS keys · more instances, sessions in Firestore", 16, "#555"))
    # outside: people and developers, GitHub
    b.append(person(110, 120, 0.85))
    b.append(text(110, 214, "People", 18, INK, 600))
    b.append(box(40, 240, 190, 90, GREY, "none", rx=2, shadow=True))
    b.append(text(135, 278, "HTTPS LB", 19, "#FFFFFF", 500))
    b.append(text(135, 304, "+ IAP sign-in", 17, "#F2F2F2"))
    b.append(path("M110,222 V240"))
    b.append(path("M230,285 H330", INK, 2.4))
    b.append(person(110, 440, 0.85))
    b.append(text(110, 534, "Developers", 18, INK, 600))
    b.append(box(40, 560, 190, 90, GREY, "none", rx=2, shadow=True))
    b.append(text(135, 598, "IAP TCP", 19, "#FFFFFF", 500))
    b.append(text(135, 624, "tunnel :3000", 17, "#F2F2F2"))
    b.append(path("M110,542 V560"))
    b.append(path("M230,605 H290 V522 H340", INK, 2.4))
    b.append(path("M530,522 H560", INK, 2.4))
    b.append(container(1460, 150, 230, 220, "GitHub", "firstround-demo", "git"))
    b.append(text(1575, 280, "pull requests", 16, "#FFFFFF"))
    b.append(text(1575, 304, "CI allow-list check", 16, "#FFFFFF"))
    b.append(text(1575, 328, "1 human review", 16, "#FFFFFF"))
    b.append(path("M600,150 V88 H1575 V150", RED, 2.6))
    b.append(label(1180, 88, "Suggest: pull request", 15, RED))
    b.append(path("M340,622 H316 V720 H1575 V370", INK, 2))
    b.append(label(1450, 720, "git over NAT", 14))
    return page("flow-3-project", W, H, "".join(b))


# ---- 4. User and access management ------------------------------------------------------

def user_mgmt():
    W, H = 1700, 760
    b = []
    lanes = [(40, "Person"), (360, "Sign-in"), (720, "Policy: role.yaml"), (1120, "What the level gets")]
    widths = [280, 320, 360, 540]
    for (x, t), w in zip(lanes, widths):
        b.append(box(x, 40, w, 680, "#BDD7EE", "none", rx=2))
        b.append(text(x + w / 2, 80, t, 22, INK, 600))
    b.append(person(180, 200, 1.0))
    b.append(text(180, 300, "A member of the team", 18, INK, 500))
    b.append(text(180, 324, "(Google account)", 16, "#333"))
    b.append(box(395, 170, 250, 120, "#FFFFFF", INK, rx=4, sw=2))
    b.append(icon_tile(410, 185, "iap", 44))
    b.append(text(540, 212, "Identity-Aware", 18, INK, 600))
    b.append(text(540, 236, "Proxy", 18, INK, 600))
    b.append(text(520, 272, "Google sign-in", 16, "#333"))
    b.append(path("M240,230 H395"))
    b.append(label(316, 222, "sign in", 15))
    b.append(box(395, 380, 250, 130, "#FFFFFF", INK, rx=4, sw=2, dash=True))
    b.append(text(520, 418, "Directory group", 18, "#555", 600))
    b.append(text(520, 444, "Entra ID / Okta", 16, "#555"))
    b.append(text(520, 468, "SAML + SCIM", 16, "#555"))
    b.append(text(520, 492, "(designed)", 15, "#777"))
    b.append(box(760, 170, 280, 150, SLATE, SLATE_LINE, rx=6, sw=2))
    b.append(text(900, 210, "Level", 22, "#FFFFFF", 600))
    b.append(text(900, 240, "Ask · Suggest", 18, "#FFFFFF"))
    b.append(text(900, 264, "Build · Govern", 18, "#FFFFFF"))
    b.append(text(900, 296, "demo: persona menu", 15, "#DDE7F0"))
    b.append(path("M645,230 H760"))
    b.append(path("M645,445 H700 V290 H760", INK, 2, dash=True))
    b.append(box(760, 380, 280, 150, "#FFFFFF", INK, rx=4, sw=2))
    b.append(text(900, 420, "Temporary access", 19, INK, 600))
    b.append(text(900, 448, "ask → approve → ends", 16, "#333"))
    b.append(text(900, 472, "by itself (≤ 8 h)", 16, "#333"))
    b.append(text(900, 504, "Govern approves", 15, PURPLE, 600))
    b.append(path("M900,380 V320"))
    grants = [("Agent tools", "write tool only at Suggest"), ("File paths", "allow-list, checked twice"),
              ("Gateway key", "models · budget · kill switch"), ("Workspace", "Build level only (Coder)"),
              ("Audit log", "every decision, hash-chained")]
    for i, (t, s) in enumerate(grants):
        y = 120 + i * 118
        b.append(slate(1160, y, 230, 84, t, 19))
        b.append(text(1410, y + 50, s, 16, INK, 400, "start"))
        b.append(path(f"M1040,245 H1100 V{y + 42} H1160", RED if i < 4 else INK, 2.4))
    for i, n in enumerate((1, 2, 3, 4)):
        b.append(step([240, 645, 1040, 1100][i] + 10, [196, 196, 196, 96][i], n, 22))
    return page("flow-4-users", W, H, "".join(b))


# ---- 5. Target architecture at enterprise scale --------------------------------------------

def enterprise_scale():
    W, H = 1920, 1060
    b = []
    # identity column
    b.append(container(30, 60, 300, 150, "Company directory", "Entra ID or Okta", "iap"))
    b.append(container(30, 270, 300, 150, "Cloud Identity groups", "synced by SCIM", "iap"))
    b.append(path("M180,210 V270"))
    b.append(label(180, 246, "SAML + SCIM", 15))
    roles_ = [("PM", "Ask"), ("Designer", "Suggest"), ("Developer", "Build"), ("Admin", "Govern")]
    for i, (r, lvl) in enumerate(roles_):
        x = 75 + (i % 2) * 150
        y = 500 + (i // 2) * 190
        b.append(person(x, y, 0.62))
        b.append(text(x, y + 72, r, 17, INK, 600))
        b.append(text(x, y + 94, lvl, 15, "#555"))
    b.append(path("M180,420 V470"))
    b.append(label(180, 452, "group = level", 15))
    b.append(step(330, 60, 1))
    # sign-in bar
    b.append(box(380, 60, 1100, 56, "#FFFFFF", INK, rx=4, sw=2))
    b.append(text(930, 96, "Google sign-in · Identity-Aware Proxy for the app and the workspaces (no VPN)", 20, INK, 500))
    b.append(path("M330,640 H360 V88 H380"))
    # perimeter
    b.append(box(380, 150, 1100, 870, "#FFFFFF", "#8E6CC8", rx=4, sw=2.5, dash=True))
    b.append(text(400, 182, "VPC Service Controls perimeter · Cloud KMS keys", 16, "#5E3BA8", 600, "start"))
    # control plane
    b.append(box(400, 200, 480, 250, BAND, BAND_LINE, rx=4, sw=2))
    b.append(text(640, 236, "RoleSpace control plane · Cloud Run", 21, INK, 500))
    for i, t in enumerate(["Assistant agents", "Requests, approvals", "Govern and usage", "Onboarding"]):
        x, y = 420 + (i % 2) * 230, 258 + (i // 2) * 88
        b.append(box(x, y, 210, 72, "#FFFFFF", GREY_LINE, rx=4))
        b.append(text(x + 105, y + 43, t, 16, INK, 600))
    b.append(step(880, 200, 2))
    # workspaces
    b.append(container(940, 200, 520, 400, "Coder on GKE · templates", "one private workspace per person", "compute"))
    st, _ = stack(985, 275, 330, 225, 3, 22, "Workspace templates", ["CLI only", "Chat UI", "CLI + chat"])
    b.append(st)
    b.append(step(1460, 200, 3))
    # gateway
    b.append(box(400, 500, 480, 330, BAND, BAND_LINE, rx=4, sw=2))
    b.append(text(640, 536, "Model gateway · LiteLLM, high availability", 20, INK, 500))
    b.append(slate(420, 560, 440, 54, "Per-person keys · budgets · rate limits", 18))
    b.append(box(420, 628, 440, 54, "#F8D7E4", "#C2185B", rx=7, sw=2))
    b.append(text(640, 662, "Model Armor: prompt and response screening", 17, INK, 500))
    b.append(slate(420, 696, 210, 54, "Cloud SQL HA", 17))
    b.append(slate(650, 696, 210, 54, "Memorystore", 17))
    b.append(text(640, 800, "Every call tagged: person · project · source", 16, "#333"))
    b.append(step(880, 500, 4))
    b.append(path("M640,450 V500", RED, 3))
    b.append(path("M940,555 H884", RED, 3))
    b.append(label(910, 540, "key", 14, RED))
    # models, reached through the egress proxy
    b.append(text(1740, 182, "Models, chosen per level", 19, INK, 600))
    models = [("Gemini on Vertex AI", "Flash · Pro"), ("Claude on Vertex AI", "Model Garden"), ("OpenAI", "customer's own key")]
    for i, (t, sub) in enumerate(models):
        y = 210 + i * 130
        b.append(box(1600, y, 280, 100, GREEN, GREEN_LINE, rx=4, sw=2))
        b.append(text(1740, y + 44, t, 20, INK, 600))
        b.append(text(1740, y + 72, sub, 16, "#444"))
    b.append(path("M880,625 H1575 V260 H1600", RED, 3.2))
    b.append(path("M1575,390 H1600", RED, 3.2))
    b.append(path("M1575,520 H1600", RED, 3.2, dash=True))
    b.append(box(1420, 607, 130, 36, SLATE, SLATE, rx=5))
    b.append(text(1485, 631, "Secure Web Proxy", 13, "#FFFFFF", 500))
    b.append(step(1880, 210, 5))
    # data and records
    b.append(box(940, 655, 520, 175, "#F3F3F3", "#9E9E9E", rx=6, sw=1.5))
    b.append(text(960, 684, "Data and records", 18, "#333", 600, "start"))
    for i, (k, t, sub) in enumerate([("store", "Firestore", "audit chain"), ("secret", "Secret Manager", "keys"),
                                      ("store", "Cloud Storage", "data drop")]):
        x = 960 + i * 165
        b.append(box(x, 698, 152, 116, "#FFFFFF", "#9E9E9E", rx=4, sw=1.5))
        b.append(icon_tile(x + 58, 706, k, 36))
        b.append(text(x + 76, 770, t, 15, INK, 600))
        b.append(text(x + 76, 796, sub, 14, "#555"))
    # usage analytics and delivery
    b.append(box(400, 860, 480, 140, "#F3F3F3", "#9E9E9E", rx=6, sw=1.5))
    b.append(text(420, 890, "Usage analytics", 18, "#333", 600, "start"))
    b.append(text(640, 930, "Spend logs → BigQuery → Looker Studio", 18, INK, 500))
    b.append(text(640, 960, "cost per person, project and outcome", 16, "#555"))
    b.append(path("M640,830 V860"))
    b.append(box(940, 860, 520, 140, "#F3F3F3", "#9E9E9E", rx=6, sw=1.5))
    b.append(text(960, 890, "Delivery", 18, "#333", 600, "start"))
    b.append(text(1200, 930, "GitHub or GitLab through a RoleSpace app:", 17, INK, 500))
    b.append(text(1200, 958, "PRs for people without accounts · CODEOWNERS · CI", 16, "#555"))
    b.append(step(1460, 860, 6))
    # outside: IaC and documents
    b.append(box(1600, 660, 280, 140, "#FFFFFF", INK, rx=2, sw=1.5, dash=True))
    b.append(text(1740, 702, "Terraform", 19, INK, 600))
    b.append(text(1740, 730, "builds every piece,", 16, "#444"))
    b.append(text(1740, 754, "one project per", 16, "#444"))
    b.append(text(1740, 778, "business unit", 16, "#444"))
    b.append(box(1600, 840, 280, 160, "#FFFFFF", INK, rx=2, sw=1.5, dash=True))
    b.append(text(1740, 880, "Data sources", 19, INK, 600))
    b.append(text(1740, 908, "Drive · SharePoint", 16, "#444"))
    b.append(text(1740, 932, "Confluence → the", 16, "#444"))
    b.append(text(1740, 956, "data drop bucket", 16, "#444"))
    b.append(path("M1600,920 H1530 V756 H1446"))
    return page("flow-5-enterprise", W, H, "".join(b))


def render(names):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_context(viewport={"width": 1800, "height": 1200}, device_scale_factor=2).new_page()
        for n in names:
            pg.goto((IMG / f"{n}.html").resolve().as_uri())
            pg.locator("svg").screenshot(path=str(IMG / f"{n}.png"))
            print("wrote", f"img/{n}.png")
        br.close()


if __name__ == "__main__":
    names = [env_flow(), work_flow(), project_arch(), user_mgmt(), enterprise_scale()]
    if "--no-render" not in sys.argv:
        render(names)
