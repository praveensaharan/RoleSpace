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
    assert roles.person_models(maya) == ["gemini-flash"]
    assert roles.person_models(leo) == ["gemini-flash", "gemini-pro"]
    assert not roles.model_enabled("claude-opus")            # listed, not switched on yet
    assert agents.pick_model(maya, "gemini-pro") == "gemini-flash"   # not on her list
    assert agents.pick_model(leo, "gemini-pro") == "gemini-pro"
    assert agents.pick_model(leo, "claude-opus") == "gemini-flash"   # not enabled


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
