"""Checks for the rules RoleSpace's claims rest on: the path allow-list, decision traces,
the citation checker and the audit hash chain. No network: run `python tests/test_core.py`
(or pytest) from the rolespace folder."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import agents  # noqa: E402
import roles  # noqa: E402
import services  # noqa: E402

SUGGEST = roles.config()["levels"]["suggest"]


def test_allow_list_accepts_designer_files():
    for path in ("public/css/app.css", "./public/css/app.css", "/public/index.html", "public/org/index.html"):
        assert roles.path_allowed(SUGGEST, path), path


def test_allow_list_refuses_code_and_traversal():
    for path in ("lib/score.mjs", "server.mjs", "public/js/ui.js", "public/css/../../server.mjs",
                 "public/css/x.css/../../../lib/score.mjs", "public/css/..%2f..%2flib/score.mjs",
                 "public\\css\\app.css", "public//css/app.css", "public/./css/app.css", "public/css/app.css\x00",
                 "", "/", "PUBLIC/css/app.css"):
        assert not roles.path_allowed(SUGGEST, path), path


def test_explain_names_the_deciding_rule():
    leo, maya = roles.person("leo"), roles.person("maya")
    denied = roles.explain(leo, "edit", "lib/score.mjs")
    assert not denied["allowed"] and denied["rule"] == "levels.suggest.deny_paths: lib/**"
    assert roles.explain(leo, "edit", "public/css/app.css")["allowed"]
    assert roles.explain(maya, "edit", "public/css/app.css")["decided_by"] == "Agent tools (role.yaml)"
    assert not roles.explain(maya, "model", "gemini-pro")["allowed"]
    assert roles.explain(roles.person("sam"), "workspace")["allowed"]


def test_elevation_is_only_what_role_yaml_allows():
    assert roles.elevation_targets("ask") == ["suggest"]
    assert roles.elevation_targets("suggest") == []
    assert roles.person("maya", "suggest")["level_cfg"]["tools"][-1] == "propose_edit"


def test_citations_must_be_read_in_full():
    convo = agents.Conversation(reads={"lib/score.mjs": set(range(1, 60))})
    ok, = agents.check_citations("Scores are clamped [lib/score.mjs:10-20].", convo)
    assert ok["ok"]
    partly, = agents.check_citations("See [lib/score.mjs:50-70].", convo)
    assert not partly["ok"] and "didn't read" in partly["reason"]
    missing, = agents.check_citations("See [lib/nope.mjs:1].", convo)
    assert missing["reason"] == "no such file"


def test_citation_parser_skips_non_citations_and_duplicates():
    convo = agents.Conversation(reads={"lib/score.mjs": set(range(1, 60))})
    assert agents.check_citations("[Note: 5] and [v1.2: 3] and [1.5:2]", convo) == []
    twice = agents.check_citations("[lib/score.mjs:3] then [lib/score.mjs:3]", convo)
    assert len(twice) == 1
    ranges = agents.check_citations("[lib/score.mjs:3-4, 8; 10–12]", convo)
    assert [(c["start"], c["end"]) for c in ranges] == [(3, 4), (8, 8), (10, 12)]


def test_models_follow_the_level_and_the_catalog():
    maya, leo = roles.person("maya"), roles.person("leo")
    assert roles.person_models(maya) == ["gemini-flash", "kimi-k2"]
    assert roles.person_models(leo) == ["gemini-flash", "gemini-pro", "kimi-k2", "qwen-coder"]
    assert not roles.model_enabled("deepseek")               # listed, not switched on yet
    assert not roles.model_enabled("claude-opus")            # not in the catalog at all
    assert agents.pick_model(maya, "gemini-pro") == "gemini-flash"   # not on her list
    assert agents.pick_model(leo, "gemini-pro") == "gemini-pro"
    assert agents.pick_model(leo, "deepseek") == "gemini-flash"      # not enabled


def _form() -> tuple[dict, dict]:
    """The policy form as the browser sends it: every level and every model's status."""
    b = roles.base()
    levels = {k: {f: v[f] for f in roles.EDITABLE} for k, v in b["levels"].items()}
    models = {k: v["status"] for k, v in b["models"].items() if v["status"] != "setup"}
    return levels, models


def test_policy_form_rules():
    levels, models = _form()
    assert roles.validate_policy(levels, models) == []
    assert roles.minimal(levels, models) == {}                        # nothing differs from role.yaml
    ask = {**levels["ask"], "models": ["gemini-flash", "deepseek"]}
    assert roles.validate_policy({**levels, "ask": ask}, models)      # DeepSeek is switched off
    assert roles.validate_policy({**levels, "ask": ask}, {**models, "deepseek": "enabled"}) == []
    assert roles.validate_policy({**levels, "ask": {**ask, "models": ["claude-sonnet"]}}, models)  # not in the catalog
    assert roles.validate_policy({**levels, "ask": {**ask, "models": []}}, models)          # no model at all
    assert roles.validate_policy({**levels, "ask": {**levels["ask"], "budget_usd": 50}}, models)
    assert roles.validate_policy({**levels, "ask": {**levels["ask"], "rpm_limit": True}}, models)
    assert roles.validate_policy(levels, {**models, "openai-codex": "enabled"})            # not in the catalog
    assert roles.validate_policy({"ask": levels["ask"]}, models)                           # every level


def test_policy_changes_sit_on_top_of_role_yaml():
    levels, models = _form()
    v0 = roles.version()
    levels["ask"] = {**levels["ask"], "models": ["gemini-flash", "deepseek"], "budget_usd": 3.0}
    o = roles.minimal(levels, {**models, "deepseek": "enabled"})
    assert o == {"levels": {"ask": {"models": ["gemini-flash", "deepseek"], "budget_usd": 3.0}},
                 "models": {"deepseek": "enabled"}}
    changes = roles.describe_changes(roles.config(), roles.merged(o))
    assert "DeepSeek V3.2 switched on" in changes and "Ask: added DeepSeek V3.2" in changes
    assert "Ask: removed Kimi K2 Thinking" in changes and "Ask: budget $2.00 → $3.00" in changes
    roles.set_overrides(o)
    try:
        assert roles.person_models(roles.person("maya")) == ["gemini-flash", "deepseek"]
        assert roles.model_enabled("deepseek") and roles.version() != v0
        assert roles.base()["levels"]["ask"]["budget_usd"] == 2.0       # the file itself is untouched
    finally:
        roles.set_overrides({})
    assert roles.version() == v0 and roles.person_models(roles.person("maya")) == ["gemini-flash", "kimi-k2"]


def test_projects_keep_their_own_files_and_rules():
    leo = roles.person("leo")
    assert agents.can_edit(leo, "firstround") and not agents.can_edit(leo, "rolespace")
    names = [t.__name__ for t in agents._tools(leo, agents.Conversation(), [], "rolespace")]
    assert "propose_edit" not in names and "read_file" in names        # no PRs outside firstround-demo
    assert not roles.explain(leo, "tool", "propose_edit", "rolespace")["allowed"]
    assert roles.explain(leo, "edit", "public/css/app.css", "firstround")["allowed"]
    convo = agents.Conversation(reads={"roles.py": set(range(1, 30))})
    ok, = agents.check_citations("See [roles.py:5-9].", convo, "rolespace")
    assert ok["ok"] and "/praveensaharan/RoleSpace/blob/" in ok["url"]
    missing, = agents.check_citations("See [roles.py:5-9].", convo, "firstround")   # not in that repo
    assert not missing["ok"]


def test_repo_access_changes_win_over_role_yaml():
    maya = roles.person("maya")
    assert roles.person_projects(maya) == ["firstround", "rolespace", "screener"]   # none listed: all
    known = {p["id"] for p in roles.people()}
    assert roles.validate_access({"maya": ["rolespace"]}, known) == []
    assert roles.validate_access({"maya": []}, known)                  # everyone works on something
    assert roles.validate_access({"maya": ["nope"]}, known) and roles.validate_access({"zed": ["rolespace"]}, known)
    v0 = roles.version()
    roles.set_access({"maya": ["rolespace"]})
    try:
        assert roles.person_projects(maya) == ["rolespace"] and roles.version() != v0
        assert roles.default_projects(maya) == ["firstround", "rolespace", "screener"]
        assert roles.person_projects(roles.person("leo")) == ["firstround", "rolespace", "screener"]
    finally:
        roles.set_access({})
    assert roles.version() == v0


def test_new_main_is_unpacked_safely():
    """A GitHub tarball is untrusted input: only regular text files, all inside the folder."""
    import io
    import tarfile
    import tempfile
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        def add(name, data=b"x = 1\n", kind=tarfile.REGTYPE, link=""):
            info = tarfile.TarInfo(name)
            info.type, info.linkname, info.size = kind, link, len(data) if kind == tarfile.REGTYPE else 0
            tar.addfile(info, io.BytesIO(data) if kind == tarfile.REGTYPE else None)
        add("owner-repo-abc/lib/score.mjs")
        add("owner-repo-abc/README.md")
        add("owner-repo-abc/../../escape.py")                       # climbs out
        add("owner-repo-abc/docs/shot.png", b"\x89PNG")              # not text
        add("owner-repo-abc/link.py", kind=tarfile.SYMTYPE, link="/etc/passwd")
        add("owner-repo-abc/.git/config")
        add("owner-repo-abc/big.json", b"x" * agents.MAX_FILE)
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d) / "snap"
        root.mkdir()
        assert agents.extract_snapshot(buf.getvalue(), root) == 2
        assert sorted(f.relative_to(root).as_posix() for f in root.rglob("*") if f.is_file()) == ["README.md", "lib/score.mjs"]
        assert not (pathlib.Path(d) / "escape.py").exists()


def test_reopened_chat_keeps_live_previews_and_context():
    key = "test-session:leo"
    agents.reset(key)
    agents._conversation(key).edits["e1"] = {"id": "e1"}
    live = agents.resume(key, [{"q": "Make the title blue", "r": {"answer": "Done, see the preview."}}])
    assert live == {"e1"}
    convo = agents.CONVERSATIONS[key]
    assert convo.session_id is None and "Make the title blue" in convo.prior and "e1" in convo.edits
    agents.reset(key)


def test_onboarding_checks_the_request():
    good = {"email": "nina@firstround.example", "name": "Nina Diaz", "team": "screening", "level": "ask",
            "projects": ["firstround"], "models": ["gemini-flash"], "budget_usd": 2}
    assert roles.validate_member(good) == []
    assert roles.member_id("Nina.Diaz@firstround.example") == "nina-diaz"
    assert roles.validate_member({**good, "email": "nina@gmail.com"})                  # other domain
    assert roles.validate_member({**good, "email": "maya@firstround.example"})         # already a member
    assert roles.validate_member({**good, "models": ["gemini-pro"]})                   # not at Ask level
    assert roles.validate_member({**good, "models": ["claude-opus"]})                  # not enabled
    assert roles.validate_member({**good, "projects": ["nope"]})
    assert roles.validate_member({**good, "budget_usd": 50})
    roles.set_members([{**good, "id": "nina", "status": "active"}])
    try:
        assert roles.person("nina")["level_cfg"]["tools"][-1] == "draft_request"
        assert roles.validate_member(good)                                             # now a duplicate
    finally:
        roles.set_members([])


def _chain(n: int) -> list[dict]:
    events, prev = [], services.GENESIS
    for i in range(n):
        rec = {"ts_iso": f"2026-10-17T12:00:0{i}+00:00", "kind": "budget_changed", "person": "ava",
               "level": "govern", "detail": f"event {i}"}
        h = services._event_hash(prev, rec)
        events.append({**rec, "id": f"e{i}", "ts": None, "prev_hash": prev, "hash": h})
        prev = h
    return events


def test_audit_chain_detects_edits_and_deletions():
    events = _chain(4)
    assert services.verify_chain(events) == {"ok": True, "checked": 4, "legacy": 0, "head": events[-1]["hash"]}
    edited = [dict(e) for e in events]
    edited[1]["detail"] = "event 1, quietly changed"
    assert services.verify_chain(edited)["event"] == "e1"
    deleted = events[:1] + events[2:]
    bad = services.verify_chain(deleted)
    assert not bad["ok"] and bad["event"] == "e2"


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"{len(tests)} checks passed")
