"""Give every person in role.yaml their own gateway key, with their level's models and budget.

The raw key is shown once by LiteLLM, so we keep it in Secret Manager as `gw-key-<id>`.
Re-running is safe: existing keys are updated in place (models, budget), not replaced.
This is also how the admin changes a budget: edit role.yaml, run this again.
It writes role.yaml's values only. If an admin changed levels in the app (Govern > Policy),
press "Push to keys" there afterwards so the keys carry the app's changes again.

    python3 gateway/provision_keys.py            # uses GATEWAY_URL, or looks it up on Cloud Run
"""

import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

import yaml

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "project-c399f432-18ea-45d7-b98")
REGION = os.getenv("REGION", "us-central1")
ID_TOKEN = ""
ROLE_FILE = pathlib.Path(__file__).resolve().parent.parent / "role.yaml"


def gcloud(*args: str, stdin: str | None = None) -> str:
    out = subprocess.run(["gcloud", *args, f"--project={PROJECT}"], input=stdin,
                         capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(out.stderr.strip())
    return out.stdout.strip()


def secret_get(name: str) -> str | None:
    """The secret's value, or None only if it doesn't exist (any other error stops the run)."""
    try:
        return gcloud("secrets", "versions", "access", "latest", f"--secret={name}")
    except RuntimeError as e:
        if "NOT_FOUND" in str(e) or "not found" in str(e).lower():
            return None
        raise


def secret_put(name: str, value: str) -> None:
    gcloud("secrets", "create", name, "--replication-policy=automatic", "--data-file=-", stdin=value)


def api(base: str, master: str, path: str, body: dict | None = None) -> dict:
    # Cloud Run checks IAM on X-Serverless-Authorization, leaving Authorization for LiteLLM's key.
    headers = {"Authorization": f"Bearer {master}", "Content-Type": "application/json",
               "X-Serverless-Authorization": f"Bearer {ID_TOKEN}"}
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{path}: HTTP {e.code} {e.read().decode()[:300]}") from None


def main() -> None:
    global ID_TOKEN
    ID_TOKEN = subprocess.run(["gcloud", "auth", "print-identity-token"], capture_output=True,
                              text=True, check=True).stdout.strip()
    base = os.getenv("GATEWAY_URL") or gcloud("run", "services", "describe", "rs-gateway",
                                              f"--region={REGION}", "--format=value(status.url)")
    master = secret_get("litellm-master-key")
    if not master:
        sys.exit("litellm-master-key is missing from Secret Manager")
    cfg = yaml.safe_load(ROLE_FILE.read_text())

    for p in cfg["people"]:
        level = cfg["levels"][p["level"]]
        user_id, alias = p["email"], f"{p['id']}-{p['level']}"
        settings = {
            "models": level["models"],
            "max_budget": level["budget_usd"],
            "budget_duration": cfg["budget_period"],
            "metadata": {"person": p["id"], "level": p["level"], "team": p["team"]},
            # Model calls only: a person's key can't reach /key/generate or other admin routes,
            # so nobody can mint themselves a key without a budget.
            "allowed_routes": ["llm_api_routes"],
            **{k: level[k] for k in ("rpm_limit", "tpm_limit") if level.get(k)},
        }
        try:
            api(base, master, f"/user/info?user_id={user_id}")
        except RuntimeError:
            api(base, master, "/user/new", {"user_id": user_id, "user_email": p["email"],
                                            "user_alias": p["name"], "user_role": "internal_user",
                                            "auto_create_key": False})

        secret = f"gw-key-{p['id']}"
        key = secret_get(secret)
        if key:
            api(base, master, "/key/update", {"key": key, "key_alias": alias, "user_id": user_id, **settings})
            action = "updated"
        else:
            key = api(base, master, "/key/generate", {"user_id": user_id, "key_alias": alias, **settings})["key"]
            secret_put(secret, key)
            action = "created"
        print(f"{action:8} {alias:14} models={','.join(level['models']):24} budget=${level['budget_usd']:.2f}"
              f"/{cfg['budget_period']}  -> secret {secret}")


if __name__ == "__main__":
    sys.exit(main())
