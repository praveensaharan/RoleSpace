"""role.yaml: who is at which level, what each level may use and touch, and why a decision
went the way it did (the same rules, explained step by step)."""

import copy
import hashlib
import json
import pathlib
import re
from functools import lru_cache

import yaml

ROLE_FILE = pathlib.Path(__file__).with_name("role.yaml")
LEVELS = ("ask", "suggest", "build", "govern")
# What an admin may change from Govern > Policy, per level. Tools and paths stay in role.yaml:
# a slip there can let edits through, so they keep the review a file change gets.
EDITABLE = ("models", "budget_usd", "rpm_limit", "tpm_limit")
LIMITS = {"budget_usd": (0, 20), "rpm_limit": (1, 1000), "tpm_limit": (1000, 20_000_000)}


@lru_cache
def source() -> str:
    return ROLE_FILE.read_text()


@lru_cache
def base() -> dict:
    """role.yaml alone, without the admin's changes."""
    return yaml.safe_load(source())


# Changes made in Govern > Policy live in Firestore and sit on top of role.yaml. Only what
# differs from the file is kept, so a later edit to role.yaml still shows through elsewhere.
_overrides: dict = {}


def overrides() -> dict:
    return copy.deepcopy(_overrides)


def set_overrides(o: dict | None) -> None:
    clean = {k: o[k] for k in ("levels", "models") if o and o.get(k)}
    if clean != _overrides:
        _overrides.clear()
        _overrides.update(copy.deepcopy(clean))
        config.cache_clear()
        version.cache_clear()


def merged(o: dict) -> dict:
    """role.yaml with a set of admin changes applied."""
    cfg = copy.deepcopy(base())
    for lvl, fields in (o.get("levels") or {}).items():
        if lvl in cfg["levels"]:
            cfg["levels"][lvl].update({k: v for k, v in fields.items() if k in EDITABLE})
    for m, status in (o.get("models") or {}).items():
        if m in cfg.get("models", {}):
            cfg["models"][m] = {**cfg["models"][m], "status": status}
    return cfg


@lru_cache
def config() -> dict:
    return merged(_overrides)


@lru_cache
def version() -> str:
    """Short fingerprint of the policy in force (role.yaml plus admin changes to levels and to
    repo access), cited by every policy decision and evidence export."""
    extra = json.dumps(_overrides, sort_keys=True) if _overrides else ""
    extra += json.dumps(_access, sort_keys=True) if _access else ""
    return hashlib.sha256((source() + extra).encode()).hexdigest()[:12]


# Repo access changed in Govern > Repo access (Firestore): person id -> the projects they may
# ask about and work on. It wins over role.yaml and onboarding; people not listed keep theirs.
_access: dict[str, list[str]] = {}


def access() -> dict[str, list[str]]:
    return {k: list(v) for k, v in _access.items()}


def set_access(a: dict | None) -> None:
    clean = {k: [x for x in v if isinstance(x, str)] for k, v in (a or {}).items() if isinstance(v, list)}
    if clean != _access:
        _access.clear()
        _access.update(clean)
        version.cache_clear()


def minimal(levels: dict, models: dict) -> dict:
    """A full policy from the form, reduced to what differs from role.yaml."""
    b, out = base(), {"levels": {}, "models": {}}
    for lvl, fields in levels.items():
        diff = {k: v for k, v in fields.items() if k in EDITABLE and v != b["levels"].get(lvl, {}).get(k)}
        if diff:
            out["levels"][lvl] = diff
    out["models"] = {m: s for m, s in models.items() if s != b.get("models", {}).get(m, {}).get("status")}
    return {k: v for k, v in out.items() if v}


def validate_policy(levels: dict, models: dict) -> list[str]:
    """Problems with a policy from the form; an empty list means it can be saved."""
    errs, b = [], base()
    catalog_ = b.get("models", {})
    if set(levels) != set(b["levels"]):
        return [f"Send every level: {', '.join(b['levels'])}."]
    for m, status in models.items():
        if m not in catalog_:
            errs.append(f"Unknown model {m}.")
        elif status not in ("enabled", "available"):
            errs.append(f"{m}: status must be enabled or available.")
        elif status == "enabled" and catalog_[m].get("status") == "setup":
            errs.append(f"{catalog_[m]['label']} needs a one-time setup first: {catalog_[m].get('note', '')}")
    status = {m: models.get(m, v.get("status", "enabled")) for m, v in catalog_.items()}
    for lvl, fields in levels.items():
        picked = fields.get("models") or []
        if not picked:
            errs.append(f"{lvl.title()} needs at least one model.")
        for m in picked:
            if m not in catalog_:
                errs.append(f"{lvl.title()}: unknown model {m}.")
            elif status[m] != "enabled":
                errs.append(f"{lvl.title()}: {catalog_[m]['label']} is switched off. Switch it on, or untick it.")
        if len(set(picked)) != len(picked):
            errs.append(f"{lvl.title()}: a model is listed twice.")
        for k, (lo, hi) in LIMITS.items():
            v = fields.get(k)
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not lo <= v <= hi:
                errs.append(f"{lvl.title()}: {k.replace('_', ' ')} must be between {lo:,} and {hi:,}.")
    return errs


def describe_changes(before: dict, after: dict) -> list[str]:
    """Plain-English list of what a policy change does, for the audit log and the confirmation."""
    out, cat = [], after.get("models", {})
    label = lambda m: (cat.get(m) or {}).get("label", m)  # noqa: E731
    for m, v in cat.items():
        was = (before.get("models", {}).get(m) or {}).get("status")
        if was != v.get("status"):
            out.append(f"{label(m)} switched {'on' if v.get('status') == 'enabled' else 'off'}")
    for lvl, a in after["levels"].items():
        b, name = before["levels"][lvl], lvl.title()
        added = [m for m in a["models"] if m not in b["models"]]
        removed = [m for m in b["models"] if m not in a["models"]]
        if added:
            out.append(f"{name}: added {', '.join(map(label, added))}")
        if removed:
            out.append(f"{name}: removed {', '.join(map(label, removed))}")
        if a["budget_usd"] != b["budget_usd"]:
            out.append(f"{name}: budget ${b['budget_usd']:.2f} → ${a['budget_usd']:.2f}")
        for k, unit in (("rpm_limit", "requests/min"), ("tpm_limit", "tokens/min")):
            if a.get(k) != b.get(k):
                out.append(f"{name}: {b.get(k) or 'no'} → {a.get(k)} {unit}")
    return out


# People added through onboarding live in Firestore; the app hands them in with set_members().
# role.yaml stays the source of truth for levels; its own people win on any id clash.
_members: list[dict] = []


def set_members(members: list[dict]) -> None:
    yaml_ids = {p["id"] for p in config()["people"]}
    _members[:] = [m for m in members if m.get("id") not in yaml_ids and m.get("status", "active") == "active"]


def _raw_people() -> list[dict]:
    return list(config()["people"]) + _members


def person(pid: str, level: str | None = None) -> dict:
    """A person from role.yaml or onboarding. `level` overrides their own level (a temporary
    elevation)."""
    for p in _raw_people():
        if p["id"] == pid:
            lvl = level or p["level"]
            return {**p, "base_level": p["level"], "level": lvl, "level_cfg": config()["levels"][lvl]}
    raise KeyError(pid)


def people() -> list[dict]:
    return [person(p["id"]) for p in _raw_people()]


# --- Models and projects -------------------------------------------------------------------

def catalog() -> dict:
    """Every model the gateway can serve, with its label, provider and status."""
    return config().get("models", {})


def model_enabled(model: str) -> bool:
    m = catalog().get(model)
    return bool(m) and m.get("status", "enabled") == "enabled"


def person_models(p: dict) -> list[str]:
    """Models this person may pick: their level's enabled models, narrowed to the ones an admin
    chose for them at onboarding (a temporary elevation uses the full level list)."""
    models = [m for m in p["level_cfg"]["models"] if model_enabled(m)]
    chosen = p.get("models")
    if chosen and p["level"] == p.get("base_level", p["level"]):
        models = [m for m in models if m in chosen] or models[:1]
    return models


def projects() -> dict:
    return config().get("projects", {})


def project_prs(project: str) -> bool:
    """Whether Suggest-level edits in this project may become pull requests (role.yaml)."""
    return bool((projects().get(project) or {}).get("pull_requests"))


def default_projects(p: dict) -> list[str]:
    """Projects from role.yaml or onboarding (all of them when none are listed)."""
    return [x for x in (p.get("projects") or list(projects())) if x in projects()]


def person_projects(p: dict) -> list[str]:
    chosen = _access.get(p["id"])
    return [x for x in chosen if x in projects()] if chosen is not None else default_projects(p)


def validate_access(changes: dict, known: set[str]) -> list[str]:
    errs = []
    for pid, picked in changes.items():
        if pid not in known:
            errs.append(f"Unknown person {pid}.")
        elif not picked:
            errs.append(f"{pid} needs at least one repository: everyone works on something.")
        elif bad := [x for x in picked if x not in projects()]:
            errs.append(f"Unknown repository {', '.join(bad)}.")
        elif len(set(picked)) != len(picked):
            errs.append(f"{pid}: a repository is listed twice.")
    return errs


def member_id(email: str) -> str:
    """A short, stable id from the email's local part (a-z, 0-9 and dashes)."""
    local = email.split("@", 1)[0].lower()
    return re.sub(r"[^a-z0-9]+", "-", local).strip("-")[:30]


def validate_member(m: dict) -> list[str]:
    """Problems with an onboarding request; an empty list means it can be provisioned."""
    errs, cfg = [], config()
    email = (m.get("email") or "").strip().lower()
    domain = cfg.get("company_domain")
    if not re.fullmatch(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", email):
        errs.append("Enter a valid work email address.")
    elif domain and not email.endswith("@" + domain):
        errs.append(f"Only {domain} email addresses can be added.")
    elif not member_id(email):
        errs.append("The email's name part must contain letters or digits.")
    elif any(p["id"] == member_id(email) or p.get("email", "").lower() == email for p in _raw_people()):
        errs.append(f"{email} is already a member.")
    if not (m.get("name") or "").strip():
        errs.append("Enter the person's name.")
    level = m.get("level")
    if level not in cfg["levels"]:
        errs.append("Choose a level.")
        return errs
    if m.get("team") not in cfg.get("teams", {}):
        errs.append("Choose a team.")
    bad = [x for x in m.get("projects") or [] if x not in projects()]
    if bad or not m.get("projects"):
        errs.append("Choose at least one project." if not bad else f"Unknown project: {', '.join(bad)}")
    allowed = [x for x in cfg["levels"][level]["models"] if model_enabled(x)]
    picked = m.get("models") or []
    if not picked or any(x not in allowed for x in picked):
        errs.append(f"Choose models from what the {level} level allows: {', '.join(allowed)}.")
    budget = m.get("budget_usd")
    if not isinstance(budget, (int, float)) or not 0 <= budget <= 20:
        errs.append("Budget must be between $0 and $20.")
    return errs


def team_owner(team: str) -> str | None:
    return (config().get("teams", {}).get(team) or {}).get("owner")


def elevation_targets(level: str) -> list[str]:
    """Levels a person may ask to hold temporarily (role.yaml `elevation`)."""
    return list((config().get("elevation", {}).get("allow") or {}).get(level, []))


def elevation_max_hours() -> float:
    return float(config().get("elevation", {}).get("max_hours", 8))


# --- Paths ------------------------------------------------------------------------------

@lru_cache(maxsize=64)
def _glob_to_regex(pattern: str) -> re.Pattern:
    # "**/" matches zero or more folders, "**" anything, "*" anything but "/".
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(f"^{out}$")


def clean_path(path: str) -> str | None:
    """A repository-relative path, or None if it could point outside the tree.

    "./public/x.css" and "/public/x.css" become "public/x.css". Anything with "..", ".",
    empty segments, backslashes, "%" escapes or control characters is refused, so a pattern like
    "public/css/**" can never be stretched to "public/css/../../lib/score.mjs".
    """
    p = (path or "").strip()
    while p.startswith("./"):
        p = p[2:]
    p = p.lstrip("/")
    if not p or "\\" in p or "%" in p or any(ord(c) < 32 for c in p):
        return None
    if any(seg in ("", ".", "..") for seg in p.split("/")):
        return None
    return p


def _first_match(patterns: list[str], path: str) -> str | None:
    return next((pat for pat in patterns if _glob_to_regex(pat).match(path)), None)


def path_allowed(level_cfg: dict, path: str) -> bool:
    """Edits are allowed only on clean paths matching the level's allow_paths, never deny_paths."""
    clean = clean_path(path)
    if clean is None or _first_match(level_cfg.get("deny_paths", []), clean):
        return False
    return _first_match(level_cfg.get("allow_paths", []), clean) is not None


# --- Explain a decision -----------------------------------------------------------------

def step(check: str, ok: bool, layer: str, rule: str = "") -> dict:
    return {"check": check, "ok": ok, "layer": layer, "rule": rule}


def decision(steps: list[dict], allowed_note: str = "") -> dict:
    failed = next((s for s in steps if not s["ok"]), None)
    return {"allowed": failed is None, "decided_by": failed["layer"] if failed else allowed_note,
            "rule": failed["rule"] if failed else "", "steps": steps, "policy_version": version()}


def _project_step(project: str) -> dict:
    name = (projects().get(project) or {}).get("name", project)
    return step(f"{name} takes pull requests from RoleSpace", project_prs(project),
                "Project settings (role.yaml)", f"projects.{project}.pull_requests")


def explain(p: dict, action: str, value: str = "", project: str | None = None) -> dict:
    """Walk the same rules the app and gateway enforce, and say which one decides.

    action: edit (value = file path) | model (value = model name) | tool (value = tool name)
            | workspace | admin
    The live gateway state (budget, suspension) is added by the caller, which can see the key.
    """
    lvl, cfg = p["level"], p["level_cfg"]
    level_rule = f"levels.{lvl}"
    first = p["name"].split()[0]
    if action == "edit":
        steps = [step(f"{lvl.title()} level has the propose_edit tool", "propose_edit" in cfg["tools"],
                       "Agent tools (role.yaml)", f"{level_rule}.tools")]
        if project:
            steps.append(_project_step(project))
        clean = clean_path(value)
        steps.append(step("Path stays inside the repository", clean is not None,
                           "Path check in code", "no '..', '.', backslash or empty segments"))
        if clean is not None:
            deny = _first_match(cfg.get("deny_paths", []), clean)
            allow = _first_match(cfg.get("allow_paths", []), clean)
            steps.append(step(f"{clean} is not on the deny list", deny is None, "Path allow-list (role.yaml)",
                               f"{level_rule}.deny_paths: {deny}" if deny else ""))
            steps.append(step(f"{clean} matches the allow list", allow is not None, "Path allow-list (role.yaml)",
                               f"{level_rule}.allow_paths: {allow}" if allow
                               else f"{level_rule}.allow_paths: {', '.join(cfg.get('allow_paths', [])) or 'none'}"))
        if all(s["ok"] for s in steps):  # what still stands between an allowed edit and main
            steps.append(step("Pull request passes the designer-allowlist CI check", True, "GitHub Actions",
                               ".github/workflows/designer-allowlist.yml"))
            steps.append(step("One human review before merge", True, "Branch protection on main"))
        return decision(steps, "Allowed as a pull request; a human merges it")
    if action == "model":
        steps = [step(f"{value} is on {first}'s gateway key", value in cfg["models"],
                       "Model gateway key", f"{level_rule}.models: {', '.join(cfg['models'])}")]
        return decision(steps, "Allowed by the gateway key")
    if action == "tool":
        steps = [step(f"{lvl.title()} level has the {value} tool", value in cfg["tools"],
                       "Agent tools (role.yaml)", f"{level_rule}.tools: {', '.join(cfg['tools'])}")]
        if project and value == "propose_edit":
            steps.append(_project_step(project))
        return decision(steps, "Tool given to the agent")
    if action == "workspace":
        steps = [step("Build level gets a Coder workspace", lvl == "build", "Coder template (key file on coder-vm)",
                       "only Build-level people get a key file from coder/sync_build_keys.sh")]
        return decision(steps, "Workspace through the IAP tunnel")
    if action == "admin":
        steps = [step("Govern level opens admin screens", lvl == "govern", "RoleSpace app", "levels.govern")]
        return decision(steps, "Admin screens")
    raise ValueError(f"unknown action {action}")
