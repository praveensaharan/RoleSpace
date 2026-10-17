"""role.yaml: who is at which level, what each level may use and touch, and why a decision
went the way it did (the same rules, explained step by step)."""

import hashlib
import pathlib
import re
from functools import lru_cache

import yaml

ROLE_FILE = pathlib.Path(__file__).with_name("role.yaml")
LEVELS = ("ask", "suggest", "build", "govern")


@lru_cache
def source() -> str:
    return ROLE_FILE.read_text()


@lru_cache
def config() -> dict:
    return yaml.safe_load(source())


@lru_cache
def version() -> str:
    """Short fingerprint of role.yaml, cited by every policy decision and evidence export."""
    return hashlib.sha256(source().encode()).hexdigest()[:12]


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
    return (catalog().get(model) or {}).get("status", "enabled") == "enabled"


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


def person_projects(p: dict) -> list[str]:
    return [x for x in (p.get("projects") or list(projects())) if x in projects()]


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


def explain(p: dict, action: str, value: str = "") -> dict:
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
        return decision(steps, "Tool given to the agent")
    if action == "workspace":
        steps = [step("Build level gets a Coder workspace", lvl == "build", "Coder template (key file on coder-vm)",
                       "only Build-level people get a key file from coder/sync_build_keys.sh")]
        return decision(steps, "Workspace through the IAP tunnel")
    if action == "admin":
        steps = [step("Govern level opens admin screens", lvl == "govern", "RoleSpace app", "levels.govern")]
        return decision(steps, "Admin screens")
    raise ValueError(f"unknown action {action}")
