"""Generate the RoleSpace HLD diagrams in the diagram-design house style.

Writes four self-contained HTML files (inline SVG) into the output directory:
  hld-1-architecture.html   secure paved road -> architecture
  hld-2-onboarding.html     swimlane: role assignment to a ready workspace
  hld-3-role-matrix.html    DP security matrix (parametric, per type spec)
  hld-4-policy-traces.html  paired policy-evaluation traces -> flowchart
"""

import math
import sys
from pathlib import Path

OUT = Path(sys.argv[1])

# ---- skin: tokens from ~/brainstrom/design.md (same as the app and the deck) ----
PAPER = "#ffffff"          # canvas
INK = "#111111"            # ink / primary
MUTED = "#6b7280"          # muted
SOFT = "#898989"           # muted-soft
ACCENT = "#3b82f6"         # brand-accent: used once per diagram, the approved-change path
ACCENT_TINT = "rgba(59,130,246,0.08)"
LINK = "#111111"           # model calls are ink: the monochrome action layer
WHITE = "#ffffff"
DARK = "#101010"           # surface-dark: the one featured box (the gateway)
ON_DARK_SOFT = "#a1a1aa"
CARD = "#f5f5f5"           # surface-card
SOFT_SURFACE = "#f8f9fa"   # surface-soft
HAIRLINE = "#e5e7eb"
LINE = "#d1d5db"           # box outline on white
ERROR = "#ef4444"
ERROR_TINT = "#fef2f2"


def ink(a):
    return f"rgba(17,17,17,{a})"


def muted(a):
    return f"rgba(107,114,128,{a})"


def soft(a):
    return f"rgba(137,137,137,{a})"


def accent(a):
    return f"rgba(239,68,68,{a})"


SANS = "'Inter', -apple-system, BlinkMacSystemFont, sans-serif"
MONO = "'JetBrains Mono', ui-monospace, monospace"
SERIF = SANS  # display type is Inter 600 with negative tracking (design.md); no serif

FONT_LINK = '<link rel="stylesheet" href="../design/tokens.css">'  # Inter + JetBrains Mono, self-hosted


def up4(v):
    return int(math.ceil(v / 4.0) * 4)


def mono_w(text, size, tracking_em=0.0):
    """Width budget for mono text: 0.62em per char plus tracking."""
    return len(text) * size * (0.62 + tracking_em)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---- page wrapper (from assets/template.html) -----------------------------
def page(slug, eyebrow, h1, subtitle, svg_w, svg_h, title, desc, body, defs_extra=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(h1)}</title>
  {FONT_LINK}
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --color-paper:   {PAPER};
      --color-ink:     {INK};
      --color-muted:   {MUTED};
      --color-accent:  {ACCENT};
      --font-sans:     {SANS};
      --font-serif:    {SERIF};
      --font-mono:     {MONO};
    }}

    body {{
      font-family: var(--font-sans);
      background: var(--color-paper);
      color: var(--color-ink);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 3rem 2rem;
    }}

    .frame {{ max-width: {svg_w}px; width: 100%; min-width: 0; }}
    .diagram-container {{ width: 100%; overflow-x: auto; }}

    .eyebrow {{
      font-family: var(--font-mono);
      font-size: 0.66rem;
      font-weight: 500;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--color-muted);
      margin-bottom: 0.5rem;
    }}

    h1 {{
      font-family: var(--font-sans);
      font-size: 36px;
      font-weight: 600;
      letter-spacing: -1px;
      line-height: 1.15;
      color: var(--color-ink);
      margin-bottom: 0.5rem;
    }}

    .subtitle {{
      font-family: var(--font-sans);
      font-size: 16px;
      line-height: 1.5;
      color: #374151;
      max-width: 60rem;
      margin-bottom: 1.5rem;
    }}

    svg {{ width: 100%; min-width: {svg_w}px; display: block; }}
    @media print {{
      .diagram-container {{ overflow-x: visible; }}
      svg {{ min-width: 0; }}
    }}
  </style>
</head>
<body>
  <div class="frame">
    <p class="eyebrow">{esc(eyebrow)}</p>
    <h1>{esc(h1)}</h1>
    <p class="subtitle">{esc(subtitle)}</p>

    <div class="diagram-container">
      <svg viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="{slug}-title {slug}-desc">
        <title id="{slug}-title">{esc(title)}</title>
        <desc id="{slug}-desc">{esc(desc)}</desc>
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{MUTED}"/></marker>
          <marker id="arrow-accent" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{ACCENT}"/></marker>
          <marker id="arrow-link" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{LINK}"/></marker>{defs_extra}
        </defs>

        <rect width="100%" height="100%" fill="{PAPER}"/>
{body}
      </svg>
    </div>
  </div>
</body>
</html>
"""


# ===========================================================================
# 1. Architecture: secure paved road (slide-16x9, presentation ramp)
# ===========================================================================
NAME_PX, SUB_PX, LABEL_PX, TAG_PX = 16, 12, 12, 8

KINDS = {
    #          fill                    stroke           tag stroke       tag text
    "focal":    (DARK,                 DARK,            "rgba(255,255,255,0.30)", ON_DARK_SOFT),
    "backend":  (WHITE,                LINE,            LINE,            MUTED),
    "store":    (CARD,                 HAIRLINE,        LINE,            MUTED),
    "external": (SOFT_SURFACE,         HAIRLINE,        LINE,            MUTED),
    "input":    (CARD,                 HAIRLINE,        LINE,            MUTED),
    "designed": ("transparent",        SOFT,            soft(0.40),      SOFT),
}
DESIGNED_LINE = f'stroke="{SOFT}" stroke-width="1.2" stroke-dasharray="6,4"'



def node(x, y, w, h, kind, tag, name, sub):
    fill, stroke, tstroke, ttext = KINDS[kind]
    cx = x + w // 2
    tw = up4(mono_w(tag, TAG_PX, 0.08) + 10)
    return f"""
        <!-- Node: {name} -->
        <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{PAPER}"/>
        <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1"{' stroke-dasharray="6,4"' if kind == 'designed' else ''}/>
        <rect x="{x + 8}" y="{y + 8}" width="{tw}" height="12" rx="2" fill="transparent" stroke="{tstroke}" stroke-width="0.8"/>
        <text x="{x + 8 + tw / 2:g}" y="{y + 17}" fill="{ttext}" font-size="{TAG_PX}" font-family="{MONO}" text-anchor="middle" letter-spacing="0.08em">{esc(tag)}</text>
        <text x="{cx}" y="{y + 44}" fill="{WHITE if kind == 'focal' else INK}" font-size="{NAME_PX}" font-weight="600" font-family="{SANS}" text-anchor="middle" letter-spacing="-0.3">{esc(name)}</text>
        <text x="{cx}" y="{y + 64}" fill="{ON_DARK_SOFT if kind == 'focal' else MUTED}" font-size="{SUB_PX}" font-family="{MONO}" text-anchor="middle">{esc(sub)}</text>"""


def label_w(text):
    return up4(mono_w(text, LABEL_PX, 0.06) + 8)


def label_h(cx, line_y, text, color, below=False):
    """Label for a horizontal segment: 6-8px gap above (or below) the line."""
    w = label_w(text)
    my = line_y + 8 if below else line_y - 6 - 16
    return f"""
        <rect x="{cx - w / 2:g}" y="{my}" width="{w}" height="16" rx="2" fill="{PAPER}"/>
        <text x="{cx}" y="{my + 12}" fill="{color}" font-size="{LABEL_PX}" font-family="{MONO}" text-anchor="middle" letter-spacing="0.06em">{esc(text)}</text>"""


def label_v(line_x, cy, text, color, side="right"):
    """Label beside a vertical segment, 8px clear of the line."""
    w = label_w(text)
    mx = line_x + 8 if side == "right" else line_x - 8 - w
    return f"""
        <rect x="{mx}" y="{cy - 8}" width="{w}" height="16" rx="2" fill="{PAPER}"/>
        <text x="{mx + w / 2:g}" y="{cy + 4}" fill="{color}" font-size="{LABEL_PX}" font-family="{MONO}" text-anchor="middle" letter-spacing="0.06em">{esc(text)}</text>"""


def zone(x, y, w, h, text, label_x):
    lw = up4(mono_w(text, TAG_PX, 0.14) + 12)
    return f"""
        <!-- Zone: {text} -->
        <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{SOFT_SURFACE}" stroke="{HAIRLINE}" stroke-width="1"/>
        <rect x="{label_x}" y="{y + 4}" width="{lw}" height="12" rx="2" fill="{SOFT_SURFACE}"/>
        <text x="{label_x + lw / 2:g}" y="{y + 13}" fill="{SOFT}" font-size="{TAG_PX}" font-family="{MONO}" text-anchor="middle" letter-spacing="0.14em">{esc(text)}</text>"""


def stop_bar(x, y):
    return f'\n        <line x1="{x}" y1="{y - 6}" x2="{x}" y2="{y + 6}" stroke="{INK}" stroke-width="2"/>'


def build_architecture():
    W, H = 1280, 720
    b = []

    # --- zones (bg -> zones -> arrows -> labels -> nodes) ---
    b.append(zone(232, 40, 768, 560, "GOOGLE CLOUD PROJECT · US-CENTRAL1", 248))
    b.append(zone(456, 88, 528, 136, "CLOUD RUN", 472))
    b.append(zone(456, 424, 232, 136, "VPC · PRIVATE SUBNET · NO PUBLIC IP", 472))
    b.append(zone(1040, 88, 216, 136, "GITHUB", 1056))

    people = (40, 296, 160, 80)
    iap_app = (248, 120, 160, 80)
    tunnel = (248, 456, 160, 80)
    app = (472, 120, 180, 80)
    gate = (744, 120, 200, 80)
    audit = (472, 272, 180, 80)
    sql = (824, 272, 160, 80)
    ws = (472, 456, 200, 80)
    gemini = (744, 456, 200, 80)
    repo = (1064, 120, 168, 80)

    b.append("\n        <!-- Arrows first (behind nodes) -->")
    # Built: Google sign-in through IAP on an HTTPS load balancer in front of the app
    b.append(f'\n        <path d="M 120,296 V 168 Q 120,160 128,160 H 248" fill="none" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    b.append(f'\n        <line x1="408" y1="152" x2="472" y2="152" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    # Built: Build-level people reach Coder only through the IAP tunnel
    b.append(f'\n        <path d="M 120,376 V 488 Q 120,496 128,496 H 248" fill="none" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    b.append(f'\n        <line x1="408" y1="496" x2="472" y2="496" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    # App and workspaces reach the gateway on the person's own key
    b.append(f'\n        <line x1="652" y1="148" x2="744" y2="148" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    b.append(f'\n        <path d="M 672,476 H 720 Q 728,476 728,468 V 192 Q 728,184 736,184 H 744" fill="none" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    # Gateway -> Gemini (the only identity with the Vertex AI role)
    b.append(f'\n        <line x1="780" y1="200" x2="780" y2="456" stroke="{LINK}" stroke-width="1.2" marker-end="url(#arrow-link)"/>')
    # Records: audit log and the gateway's keys and spend
    b.append(f'\n        <line x1="562" y1="200" x2="562" y2="272" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    b.append(f'\n        <line x1="904" y1="200" x2="904" y2="272" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    # App -> GitHub: the approved change path (headline)
    b.append(f'\n        <path d="M 600,120 V 80 Q 600,72 608,72 H 1140 Q 1148,72 1148,80 V 120" fill="none" stroke="{ACCENT}" stroke-width="1.4" marker-end="url(#arrow-accent)"/>')
    # Blocked: a workspace calling Gemini directly (403, no Vertex AI role)
    b.append(f'\n        <line x1="672" y1="516" x2="736" y2="516" stroke="{INK}" stroke-width="1.2" stroke-dasharray="4,3"/>')
    b.append(stop_bar(738, 516))

    b.append("\n\n        <!-- Arrow labels -->")
    b.append(label_h(184, 160, "SIGN-IN", SOFT))
    b.append(label_h(184, 496, "BUILD ONLY", SOFT, below=True))
    b.append(label_h(440, 496, ":3000", SOFT, below=True))
    b.append(label_h(698, 148, "OWN KEY", SOFT))
    b.append(label_v(728, 400, "OWN KEY", SOFT, side="left"))
    b.append(label_v(780, 408, "ONLY PATH", LINK))
    b.append(label_v(562, 240, "AUDIT", SOFT))
    b.append(label_v(904, 240, "SPEND", SOFT))
    b.append(label_h(874, 72, "PULL REQUEST · SUGGEST", ACCENT))
    b.append(label_h(704, 516, "× 403", INK, below=True))

    # Designed-only production pieces, inside the project
    b.append(f"""

        <!-- Designed, not built -->
        <rect x="248" y="560" width="736" height="28" rx="4" fill="transparent" {DESIGNED_LINE}/>
        <text x="616" y="578" fill="{SOFT}" font-size="12" font-family="{MONO}" text-anchor="middle">DESIGNED, NOT BUILT · Entra ID group sync (SAML, SCIM) · Model Armor · Cloud KMS keys</text>""")

    b.append(f"""

        <!-- Callout -->
        <text x="1040" y="476" fill="{INK}" font-size="16" font-weight="600" letter-spacing="-0.3" font-family="{SANS}">Only the gateway's service</text>
        <text x="1040" y="496" fill="{INK}" font-size="16" font-weight="600" letter-spacing="-0.3" font-family="{SANS}">account may call Gemini.</text>
        <path d="M 1036 486 Q 1000 488 948 494" fill="none" stroke="{ink(0.40)}" stroke-width="1" stroke-dasharray="4,3"/>""")

    b.append(node(*people, "input", "USER", "People, by level", "Ask · Suggest · Build"))
    b.append(node(*iap_app, "external", "IAP · LB", "Google sign-in", "HTTPS load balancer"))
    b.append(node(*tunnel, "external", "IAP", "IAP tunnel", "to Coder · no VPN"))
    b.append(node(*app, "backend", "APP", "RoleSpace app", "Ask · Suggest · Govern"))
    b.append(node(*gate, "focal", "GATE", "Model gateway", "LiteLLM · keys · budget"))
    b.append(node(*audit, "store", "FIRESTORE", "Audit log", "hash-chained"))
    b.append(node(*sql, "store", "CLOUD SQL", "Keys and spend", "rs-sql · Postgres"))
    b.append(node(*ws, "backend", "VM", "Coder workspaces", "Gemini CLI · VS Code"))
    b.append(node(*gemini, "external", "VERTEX AI", "Gemini", "Flash · Pro"))
    b.append(node(*repo, "external", "REPO", "firstround-demo", "CI check · 1 review"))

    b.append(legend_strip(
        624,
        [("focal", "Gateway"), ("backend", "Service"), ("store", "Record"),
         ("external", "Managed"), ("input", "Person"), ("designed", "Designed only")],
        [(f'stroke="{ACCENT}" stroke-width="1.4" marker-end="url(#arrow-accent)"', "Change as PR", False),
         (f'stroke="{LINK}" stroke-width="1.2" marker-end="url(#arrow-link)"', "Model call", False),
         (f'stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"', "Call", False),
         (f'stroke="{SOFT}" stroke-width="1.2" stroke-dasharray="6,4" marker-end="url(#arrow)"', "Designed", False),
         (f'stroke="{INK}" stroke-width="1.2" stroke-dasharray="4,3"', "Blocked", True)],
    ))

    slug = "hld-1-architecture"
    html = page(
        slug,
        "RoleSpace · High-level design · 1 of 4 · Architecture (as built, 17 Oct 2026)",
        "Every model call goes through one gateway",
        "What runs today on Google Cloud. The RoleSpace app and the LiteLLM model gateway run on Cloud Run; Coder workspaces run "
        "on a VM in a private subnet with no public IP, reached only through an IAP tunnel. People sign in with Google through IAP "
        "on an HTTPS load balancer. Only the gateway's service account may call Gemini, and every call is charged to the person's "
        "own key. The demo codebase is praveensaharan/firstround-demo. Dashed parts are designed but not built: Entra ID sync, "
        "Model Armor and Cloud KMS.",
        W, H,
        "RoleSpace architecture on Google Cloud, as built",
        "People sign in with Google through IAP on an HTTPS load balancer to reach the RoleSpace app on Cloud Run and, at the Build level, Coder "
        "workspaces in a private subnet through an IAP tunnel; both reach Gemini only through a LiteLLM gateway on Cloud Run with "
        "each person's key, which records keys and spend in Cloud SQL; the app writes an audit log to Firestore and opens pull "
        "requests on firstround-demo; a workspace calling Gemini directly is refused with 403.",
        "".join(b),
    )
    (OUT / f"{slug}.html").write_text(html)


def legend_strip(ly, swatches, lines):
    out = [f"""

        <!-- Legend strip -->
        <line x1="40" y1="{ly}" x2="1240" y2="{ly}" stroke="{ink(0.10)}" stroke-width="0.8"/>
        <text x="40" y="{ly + 20}" fill="{MUTED}" font-size="8" font-family="{MONO}" letter-spacing="0.18em">LEGEND</text>"""]
    iy = ly + 44
    x = 40
    for kind, text in swatches:
        fill, stroke, _, _ = KINDS[kind]
        dash = ' stroke-dasharray="3,2"' if kind == "designed" else ""
        out.append(f'\n        <rect x="{x}" y="{iy - 10}" width="16" height="12" rx="2" fill="{fill}" stroke="{stroke}" stroke-width="1"{dash}/>')
        out.append(f'\n        <text x="{x + 24}" y="{iy}" fill="{MUTED}" font-size="10" font-family="{SANS}">{esc(text)}</text>')
        x = up4(x + 24 + len(text) * 5.6 + 24)
    for attrs, text, bar in lines:
        out.append(f'\n        <line x1="{x}" y1="{iy - 4}" x2="{x + 28}" y2="{iy - 4}" {attrs}/>')
        if bar:
            out.append(f'\n        <line x1="{x + 30}" y1="{iy - 10}" x2="{x + 30}" y2="{iy + 2}" stroke="{INK}" stroke-width="2"/>')
        out.append(f'\n        <text x="{x + 40}" y="{iy}" fill="{MUTED}" font-size="10" font-family="{SANS}">{esc(text)}</text>')
        x = up4(x + 40 + len(text) * 5.6 + 24)
    return "".join(out)


# ===========================================================================
# 2. Onboarding and identity: swimlane (slide-16x9, presentation ramp)
# ===========================================================================
def build_onboarding():
    W, H = 1280, 720
    lanes = [("PEOPLE", 56), ("IDENTITY", 176), ("GATEWAY", 296), ("WORKSPACE", 416)]
    lane_h = 120
    b = []

    # phase headers and divider
    b.append(f"""
        <!-- Phases -->
        <text x="176" y="40" fill="{MUTED}" font-size="12" font-family="{MONO}" letter-spacing="0.12em">PROVISIONING · BEFORE DAY ONE</text>
        <text x="800" y="40" fill="{MUTED}" font-size="12" font-family="{MONO}" letter-spacing="0.12em">DAY ONE</text>
        <line x1="776" y1="56" x2="776" y2="536" stroke="{ink(0.20)}" stroke-width="1" stroke-dasharray="4,4"/>""")
    # lane dividers and labels
    for name, y in lanes:
        b.append(f'\n        <line x1="40" y1="{y}" x2="1240" y2="{y}" stroke="{ink(0.12)}" stroke-width="0.8"/>')
        b.append(f'\n        <text x="48" y="{y + lane_h // 2 + 3}" fill="{SOFT}" font-size="8" font-family="{MONO}" letter-spacing="0.14em">{esc(name)}</text>')
    b.append(f'\n        <line x1="40" y1="536" x2="1240" y2="536" stroke="{ink(0.12)}" stroke-width="0.8"/>')

    # arrows
    b.append("\n\n        <!-- Arrows first (behind nodes) -->")
    b.append(f'\n        <path d="M 336,116 H 428 Q 436,116 436,124 V 316" fill="none" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    b.append(f'\n        <line x1="256" y1="196" x2="256" y2="160" {DESIGNED_LINE} marker-end="url(#arrow)"/>')
    b.append(f'\n        <path d="M 544,356 H 664 Q 672,356 672,364 V 436" fill="none" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    b.append(f'\n        <line x1="880" y1="156" x2="880" y2="196" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    b.append(f'\n        <line x1="880" y1="276" x2="880" y2="436" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    b.append(f'\n        <line x1="752" y1="476" x2="800" y2="476" stroke="{MUTED}" stroke-width="1" stroke-dasharray="4,3" marker-end="url(#arrow)"/>')
    b.append(f'\n        <path d="M 960,476 H 1112 Q 1120,476 1120,468 V 396" fill="none" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')

    # labels
    b.append("\n\n        <!-- Arrow labels -->")
    b.append(label_v(436, 236, "PROVISION", SOFT, side="left"))
    b.append(label_v(256, 178, "PRODUCTION", SOFT))
    b.append(label_v(672, 404, "BUILD ONLY", SOFT))
    b.append(label_v(880, 176, "NO VPN", SOFT))
    b.append(label_v(880, 356, "IAP TUNNEL", SOFT))
    b.append(label_h(776, 476, "KEY", SOFT, below=True))
    b.append(label_h(1040, 476, "OWN KEY", SOFT))

    # nodes
    b.append(node(176, 76, 160, 80, "input", "ADMIN", "Edit role.yaml", "Sam → Build"))
    b.append(node(176, 196, 160, 80, "designed", "DESIGNED", "Entra ID groups", "SAML · SCIM sync"))
    b.append(node(384, 316, 160, 80, "focal", "GATE", "Gateway key", "models · $ budget"))
    b.append(node(592, 436, 160, 80, "backend", "VM", "Build key on VM", "sync_build_keys.sh"))
    b.append(node(800, 76, 160, 80, "input", "USER", "Sam opens Coder", "browser, day one"))
    b.append(node(800, 196, 160, 80, "external", "IAP", "IAP admits", "Google identity"))
    b.append(node(800, 436, 160, 80, "backend", "VM", "Workspace ready", "~30 s · Gemini CLI"))
    b.append(node(1040, 316, 160, 80, "store", "LEDGER", "First call logged", "Govern: per person"))

    b.append(legend_strip(
        576,
        [("focal", "Per-person key"), ("backend", "Service"), ("store", "Record"),
         ("external", "Managed"), ("input", "Person"), ("designed", "Designed only")],
        [(f'stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"', "Step", False),
         (f'stroke="{MUTED}" stroke-width="1" stroke-dasharray="4,3" marker-end="url(#arrow)"', "Read at create", False)],
    ))

    slug = "hld-2-onboarding"
    html = page(
        slug,
        "RoleSpace · High-level design · 2 of 4 · Onboarding (as built, 17 Oct 2026)",
        "From a line in role.yaml to a ready workspace",
        "Today an admin gives a person a level in role.yaml. provision_keys.py creates their gateway key with the level's models "
        "and budget; for Build, sync_build_keys.sh puts the key on the Coder VM, and only people with a key there can create a "
        "workspace. On day one the developer opens Coder through the IAP tunnel, with no VPN; the workspace is ready in about 30 "
        "seconds with Gemini CLI on their own key, and their first call shows in Govern. In production, groups would sync from "
        "Entra ID (dashed: designed, not built).",
        W, H,
        "RoleSpace onboarding flow as built",
        "Swimlane: an admin edits role.yaml, provision_keys.py creates the person's gateway key with models and budget, "
        "sync_build_keys.sh copies Build keys to the Coder VM; on day one the developer opens Coder through the IAP tunnel, "
        "the workspace is ready with Gemini CLI on their key, and the first call is logged per person; Entra ID group sync "
        "is designed only.",
        "".join(b),
    )
    (OUT / f"{slug}.html").write_text(html)


# ===========================================================================
# 3. Role matrix: DP security matrix, deterministic geometry from the type spec
# ===========================================================================
LEVEL_PASTEL = {"ASK": "#34d399", "SUGGEST": "#8b5cf6", "BUILD": "#fb923c", "GOVERN": "#3b82f6"}


def build_matrix():
    roles = [
        ("Maya · PM", "ASK"),
        ("Leo · designer", "SUGGEST"),
        ("Sam · developer", "BUILD"),
        ("Ava · admin", "GOVERN"),
    ]
    components = [
        ("Read code, docs", "agent tools"),
        ("Edit files", "propose_edit"),
        ("Open a PR", "after a preview"),
        ("Merge to main", "branch rules"),
        ("Workspace", "Coder · IAP"),
        ("Models on key", "gateway"),
        ("Budget, 30 days", "gateway"),
        ("Spend, audit", "Govern"),
    ]
    # (value, level) per row, per role column; focal is (value, "focal", sub)
    cells = [
        [("Read · lines checked", "read"), ("Read", "read"), ("Read · own workspace", "read"), ("Read", "read")],
        [("No write tool", "focal", "enforced in code"), ("public/css, *.html", "rw"), ("In own workspace", "full"), ("No write tool", "none")],
        [("Drafts a request", "read"), ("Yes, CI-checked", "rw"), ("Drafts a request", "read"), ("Drafts a request", "read")],
        [("No", "none"), ("No", "none"), ("1 human review", "full"), ("No", "none")],
        [("Refused", "none"), ("Refused", "none"), ("Own, via IAP", "full"), ("Refused", "none")],
        [("Flash", "read"), ("Flash, Pro", "rw"), ("Flash, Pro", "rw"), ("Flash", "read")],
        [("$2", "read"), ("$1", "read"), ("$10", "read"), ("Sets everyone's", "full")],
        [("Own key", "read"), ("Own key", "read"), ("Own key", "read"), ("All people", "full")],
    ]

    left_pad, right_pad = 12, 48
    comp_col_w, comp_role_gap = 208, 12
    role_col_w, role_col_gap = 148, 16
    header_h, row_h, row_stride = 52, 36, 40
    n_roles, n_comp = len(roles), len(components)
    W = left_pad + comp_col_w + comp_role_gap + n_roles * role_col_w + (n_roles - 1) * role_col_gap + right_pad
    header_y = 72

    def row_y(k):
        return 140 + k * row_stride

    rows_bottom = row_y(n_comp - 1) + row_h
    legend_y_top = rows_bottom + 20
    H = legend_y_top + 44

    def role_col_x(j):
        return left_pad + comp_col_w + comp_role_gap + j * (role_col_w + role_col_gap)

    styles = {
        "full": (CARD, INK, "600"),
        "rw": (WHITE, INK, "400"),
        "read": (SOFT_SURFACE, MUTED, "400"),
        "none": (WHITE, SOFT, "400"),
    }

    b = []
    # header cell
    b.append(f"""
        <!-- Header row -->
        <rect x="{left_pad}" y="{header_y}" width="{comp_col_w}" height="{header_h}" rx="6" fill="{WHITE}" stroke="{ink(0.12)}" stroke-width="0.8"/>
        <text x="{left_pad + comp_col_w // 2}" y="{header_y + 24}" fill="{INK}" font-size="11" font-weight="600" font-family="{SANS}" text-anchor="middle">Capability</text>
        <text x="{left_pad + comp_col_w // 2}" y="{header_y + 40}" fill="{MUTED}" font-size="9" font-family="{MONO}" text-anchor="middle">vs. role level</text>""")
    for j, (name, code) in enumerate(roles):
        x = role_col_x(j)
        cx = x + role_col_w // 2
        b.append(f"""
        <rect x="{x}" y="{header_y}" width="{role_col_w}" height="{header_h}" rx="12" fill="{CARD}"/>
        <text x="{cx}" y="92" fill="{INK}" font-size="12" font-weight="600" font-family="{SANS}" text-anchor="middle">{esc(name)}</text>
        <rect x="{cx - 30}" y="98" width="60" height="16" rx="8" fill="{LEVEL_PASTEL[code]}"/>
        <text x="{cx}" y="110" fill="{INK}" font-size="9" font-weight="500" font-family="{SANS}" text-anchor="middle">{esc(code.title())}</text>""")

    used = set()
    for k, (cname, hint) in enumerate(components):
        y = row_y(k)
        b.append(f"""
        <!-- Row {k}: {cname} -->
        <rect x="{left_pad}" y="{y}" width="{comp_col_w}" height="{row_h}" rx="4" fill="{WHITE}" stroke="{ink(0.12)}" stroke-width="0.8"/>
        <text x="{left_pad + 12}" y="{y + 22}" fill="{INK}" font-size="11" font-weight="600" font-family="{SANS}">{esc(cname)}</text>
        <text x="{left_pad + comp_col_w - 12}" y="{y + 22}" fill="{MUTED}" font-size="9" font-family="{MONO}" text-anchor="end">{esc(hint)}</text>""")
        for j, cell in enumerate(cells[k]):
            x = role_col_x(j)
            cx = x + role_col_w // 2
            if cell[1] == "focal":
                used.add("focal")
                b.append(f"""
        <rect x="{x}" y="{y}" width="{role_col_w}" height="{row_h}" rx="6" fill="{DARK}"/>
        <text x="{cx}" y="{y + 18}" fill="{WHITE}" font-size="10" font-weight="600" font-family="{SANS}" text-anchor="middle">{esc(cell[0])}</text>
        <text x="{cx}" y="{y + 30}" fill="{ON_DARK_SOFT}" font-size="8" font-family="{MONO}" text-anchor="middle">{esc(cell[2])}</text>""")
            else:
                value, level = cell
                used.add(level)
                fill, color, weight = styles[level]
                b.append(f"""
        <rect x="{x}" y="{y}" width="{role_col_w}" height="{row_h}" rx="4" fill="{fill}" stroke="{ink(0.12)}" stroke-width="0.6"/>
        <text x="{cx}" y="{y + 22}" fill="{color}" font-size="10" font-weight="{weight}" font-family="{SANS}" text-anchor="middle">{esc(value)}</text>""")

    # legend: only the levels used
    b.append(f"""

        <!-- Legend strip -->
        <line x1="{left_pad}" y1="{legend_y_top}" x2="{W - right_pad}" y2="{legend_y_top}" stroke="{ink(0.10)}" stroke-width="0.8"/>
        <text x="{left_pad}" y="{legend_y_top + 20}" fill="{MUTED}" font-size="8" font-family="{MONO}" letter-spacing="0.14em">LEGEND</text>""")
    legend = [
        ("full", "Full control", CARD, ink(0.12), 0.6),
        ("rw", "Can change", WHITE, ink(0.12), 0.6),
        ("read", "Read or limited", SOFT_SURFACE, ink(0.12), 0.6),
        ("none", "No access", PAPER, ink(0.30), 0.6),
        ("focal", "Core rule", DARK, DARK, 1),
    ]
    x = left_pad + 80
    for level, text, fill, stroke, sw in legend:
        if level not in used:
            continue
        b.append(f"""
        <rect x="{x}" y="{legend_y_top + 10}" width="14" height="12" rx="2" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>
        <text x="{x + 20}" y="{legend_y_top + 20}" fill="{MUTED}" font-size="9" font-family="{MONO}">{esc(text)}</text>""")
        x += 140

    slug = "hld-3-role-matrix"
    html = page(
        slug,
        "RoleSpace · High-level design · 3 of 4 · Role ladder (as built, from role.yaml)",
        "The role ladder: what each level can do",
        "Each person gets one level in role.yaml. The level decides which tools their agent has (enforced in code), which models "
        "and budget their gateway key allows (enforced by the gateway), and whether they get a Coder workspace. Designer edits are "
        "limited to public/css/** and public/**/*.html, checked again in CI; every merge needs one human review.",
        W, H,
        "RoleSpace role permissions",
        "Permission matrix for the four RoleSpace levels: the PM's agent has no write tool, the designer can change only "
        "public/css and HTML files through checked pull requests, the developer has a workspace with Gemini CLI, and only "
        "the platform admin sets budgets and sees everyone's spend and the audit log.",
        "".join(b),
    )
    (OUT / f"{slug}.html").write_text(html)


# ===========================================================================
# 4. Paired policy-evaluation traces (slide-16x9, presentation ramp)
# ===========================================================================
def build_traces():
    W, H = 1280, 720
    xs = (600, 840, 1080)         # trace centre lines
    cw, chh = 196, 48             # status cell size
    traces = [
        ("A · Leo (Suggest)", "Begin button → #FF6B35"),
        ("B · Leo (Suggest)", "score out of 10"),
        ("C · Maya (Ask)", "passing score → 40"),
    ]
    rules = [
        # name, sub, row y, (A, B, C) as (status, detail)
        ("1 · Level from sign-in", "persona → role.yaml", 136, (("pass", "Suggest"), ("pass", "Suggest"), ("pass", "Ask"))),
        ("2 · Budget left", "gateway checks the key", 208, (("pass", "within $1"), ("pass", "within $1"), ("pass", "within $2"))),
        ("3 · Tool exists at level", "Ask has no write tool", 280, (("pass", "propose_edit"), ("pass", "propose_edit"), ("fail", "no write tool"))),
        ("4 · Path on allow-list", "public/css/**, public/**/*.html", 352, (("pass", "public/css/app.css"), ("fail", "lib/score.mjs"), ("nr", ""))),
        ("5 · Preview, then PR", "CI check + 1 human review", 424, (("pass", "PR opened"), ("nr", ""), ("nr", ""))),
    ]
    rh = 64

    b = []
    b.append(f"""
        <!-- Column headers -->
        <text x="64" y="88" fill="{MUTED}" font-size="12" font-family="{MONO}" letter-spacing="0.12em">CHECKS, IN ORDER</text>
        <text x="64" y="108" fill="{SOFT}" font-size="12" font-family="{MONO}">app code, gateway, then GitHub</text>""")
    for name, sub, ry, _ in rules:
        b.append(f'\n        <rect x="48" y="{ry}" width="1184" height="{rh}" rx="8" fill="{SOFT_SURFACE}"/>')

    # trace lines run down to the rule where each request stops
    stops = []
    for k in range(3):
        last = max(i for i, r in enumerate(rules) if r[3][k][0] != "nr")
        stops.append(last)
        b.append(f'\n        <line x1="{xs[k]}" y1="112" x2="{xs[k]}" y2="{rules[last][2] + 8 + chh}" stroke="{ink(0.30)}" stroke-width="1"/>')
        b.append(f'\n        <line x1="{xs[k]}" y1="{rules[last][2] + 8 + chh}" x2="{xs[k]}" y2="520" stroke="{ink(0.30)}" stroke-width="1" stroke-dasharray="2,4"/>')

    for (title, req), cx in zip(traces, xs):
        b.append(f"""
        <rect x="{cx - 112}" y="48" width="224" height="64" rx="6" fill="{WHITE}" stroke="{INK}" stroke-width="1"/>
        <text x="{cx}" y="76" fill="{INK}" font-size="16" font-weight="600" font-family="{SANS}" text-anchor="middle">{esc(title)}</text>
        <text x="{cx}" y="96" fill="{MUTED}" font-size="12" font-family="{MONO}" text-anchor="middle">{esc(req)}</text>""")

    def cell(cx, y, status, detail):
        x = cx - cw // 2
        if status == "pass":
            box = (f'<rect x="{x}" y="{y}" width="{cw}" height="{chh}" rx="4" fill="{PAPER}"/>'
                   f'\n        <rect x="{x}" y="{y}" width="{cw}" height="{chh}" rx="6" fill="{CARD}" stroke="{HAIRLINE}" stroke-width="1"/>')
            head, col = "✓ PASS", INK
        elif status == "fail":
            box = (f'<rect x="{x}" y="{y}" width="{cw}" height="{chh}" rx="4" fill="{PAPER}"/>'
                   f'\n        <rect x="{x}" y="{y}" width="{cw}" height="{chh}" rx="6" fill="{ERROR_TINT}" stroke="{ERROR}" stroke-width="1.2"/>')
            head, col = "× FAIL", ERROR
        else:
            box = f'<rect x="{x}" y="{y}" width="{cw}" height="{chh}" rx="4" fill="{PAPER}" stroke="{ink(0.30)}" stroke-width="1" stroke-dasharray="4,4"/>'
            head, col = "○ NOT REACHED", SOFT
        out = f"\n        {box}"
        if detail:
            out += f'\n        <text x="{cx}" y="{y + 20}" fill="{col}" font-size="12" font-weight="600" font-family="{MONO}" text-anchor="middle">{head}</text>'
            out += f'\n        <text x="{cx}" y="{y + 38}" fill="{MUTED if status != "fail" else ERROR}" font-size="11" font-family="{MONO}" text-anchor="middle">{esc(detail)}</text>'
        else:
            out += f'\n        <text x="{cx}" y="{y + 28}" fill="{col}" font-size="12" font-weight="600" font-family="{MONO}" text-anchor="middle">{head}</text>'
        return out

    for name, sub, ry, statuses in rules:
        b.append(f"""
        <!-- Rule: {name} -->
        <text x="64" y="{ry + 28}" fill="{INK}" font-size="16" font-weight="600" font-family="{SANS}">{esc(name)}</text>
        <text x="64" y="{ry + 48}" fill="{MUTED}" font-size="12" font-family="{MONO}">{esc(sub)}</text>""")
        for cx, st in zip(xs, statuses):
            b.append(cell(cx, ry + 8, *st))

    # outcomes
    oy = 520
    outcomes = [("Permitted · PR opened", True), ("Denied by policy", False), ("Refused · request drafted", False)]
    for cx, (text, ok) in zip(xs, outcomes):
        fill, tcol, scol = (DARK, WHITE, ON_DARK_SOFT) if ok else (WHITE, INK, MUTED)
        b.append(f"""
        <rect x="{cx - 112}" y="{oy}" width="224" height="64" rx="6" fill="{fill}" stroke="{INK}" stroke-width="1.2"/>
        <text x="{cx}" y="{oy + 24}" fill="{scol}" font-size="12" font-family="{MONO}" text-anchor="middle" letter-spacing="0.12em">OUTCOME</text>
        <text x="{cx}" y="{oy + 46}" fill="{tcol}" font-size="16" font-weight="600" font-family="{SANS}" text-anchor="middle">{esc(text)}</text>""")

    ly = 616
    b.append(f"""

        <!-- Legend strip -->
        <line x1="64" y1="{ly}" x2="1216" y2="{ly}" stroke="{ink(0.12)}" stroke-width="0.8"/>
        <text x="64" y="{ly + 28}" fill="{INK}" font-size="12" font-family="{MONO}">✓ PASS</text>
        <text x="168" y="{ly + 28}" fill="{ERROR}" font-size="12" font-family="{MONO}">× FAIL · request stops here, logged to the audit log</text>
        <text x="600" y="{ly + 28}" fill="{SOFT}" font-size="12" font-family="{MONO}">○ NOT REACHED · stopped at an earlier rule</text>
        <text x="64" y="{ly + 52}" fill="{MUTED}" font-size="12" font-family="{MONO}">Rules 3 and 4 are code, not the prompt: the Ask agent has no write tool, and propose_edit checks the path before anything reaches GitHub.</text>""")

    slug = "hld-4-policy-traces"
    html = page(
        slug,
        "RoleSpace · High-level design · 4 of 4 · Policy checks (as tested, 17 Oct 2026)",
        "Three change requests, one policy: where each one stops",
        "The demo's three requests on firstround-demo run the same checks in the same order. Leo's colour change passes every "
        "check and becomes a pull request. His change to lib/score.mjs stops at the path allow-list. Maya's request stops one "
        "rule earlier, because the Ask level has no write tool, so her agent refuses and drafts a request to the team instead.",
        W, H,
        "Policy evaluation for three change requests",
        "Three traces through five checks: the designer's CSS change passes all five and becomes a pull request; the designer's "
        "lib/score.mjs change passes the first three and fails the path allow-list; the PM's change fails at the tool check because "
        "the Ask level has no write tool, and is refused with a drafted request.",
        "".join(b),
    )
    (OUT / f"{slug}.html").write_text(html)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    build_architecture()
    build_onboarding()
    build_matrix()
    build_traces()
    print("wrote", sorted(p.name for p in OUT.glob("hld-*.html")))
