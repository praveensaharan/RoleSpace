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


def person(pid: str, level: str | None = None) -> dict:
    """A person from role.yaml. `level` overrides their own level (a temporary elevation)."""
    for p in config()["people"]:
        if p["id"] == pid:
            lvl = level or p["level"]
            return {**p, "base_level": p["level"], "level": lvl, "level_cfg": config()["levels"][lvl]}
    raise KeyError(pid)


def people() -> list[dict]:
    return [person(p["id"]) for p in config()["people"]]


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
