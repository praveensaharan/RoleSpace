# Security model

RoleSpace never trusts the prompt to keep anyone inside their level. Each limit is enforced by something the model can't talk its way past, and most limits are enforced twice.

## Layers

| # | Layer | Where | Enforces |
|---|---|---|---|
| 1 | Sign-in | IAP on the HTTPS load balancer | Only signed-in Google accounts reach the app. Cloud Run accepts traffic only from the load balancer. |
| 2 | Agent tools | `agents.py` | Each agent gets only its level's tools from `role.yaml`. A `before_tool_callback` refuses anything else and logs it. |
| 3 | Path policy | `roles.clean_path`, `roles.path_allowed` | Edits must match `allow_paths` and must not match `deny_paths`. Paths with `..`, `.`, `%`, backslashes or empty segments are refused. The check runs when the edit is proposed and again before anything is written to GitHub. |
| 4 | Model gateway | LiteLLM on Cloud Run | Each person's key carries their models, budget, rate limits and a block flag. Keys reach model routes only (`allowed_routes: [llm_api_routes]`), so a key can't create another key. A hard ceiling caps all AI spend together, every 30 days. The gateway itself sits behind Cloud Run IAM. |
| 5 | IAM | Google Cloud | Only the gateway's service account has the Vertex AI role, so the app and the workspace VM get 403 if they call Gemini directly. The app and the gateway each read only the secrets they need, one grant per secret. The app may add versions only to secrets named `gw-key-*`. |
| 6 | CI and review | GitHub | The `designer-allowlist` check fails bot PRs that touch files outside the allow-list. Branch protection requires one human review. |
| 7 | Network | VPC | The Coder VM has no public IP and sits in a private subnet. Inbound traffic comes only from Google's IAP range on ports 22 and 3000. Workspace containers can't reach the VM's metadata server, so they can't borrow its Google identity (`rolespace-metadata-block` in `coder/setup-vm.sh`). The relay forwards model routes only. |
| 8 | Spending cap | Cloud Billing budget, Pub/Sub, Cloud Run (`billing_cap/`) | When armed, billing for the whole project is unlinked as the month's spend nears the limit, so every paid service stops. Deployed in dry-run. |

## Other protections

- **Verified citations.** A `[file:line]` citation counts only if the file exists, the lines exist and the agent read every one of them. Otherwise it is struck out on screen.
- **Prompt injection.** Text in repository files is data. Instruction-like text is flagged, logged (`injection_ignored`) and not followed. If an agent did follow it, layers 3, 4 and 6 still stand.
- **Temporary access.** An elevation is limited to what `role.yaml` allows (Ask to Suggest, at most 8 hours). It needs a Govern-level approval, is recorded before the key changes, and ends by itself.
- **Tamper-evident audit.** Each Firestore event stores the SHA-256 of the previous event. The Audit log page checks the chain, and the evidence pack explains how to recompute it.
- **Secrets.** Every key and token lives in Secret Manager. Secrets are re-read every 10 minutes, so a rotated secret is picked up. Keys never appear in URLs or logs.
- **Web.** The app sends a strict Content-Security-Policy (no inline scripts), HSTS, `X-Frame-Options: DENY` and `nosniff`. All server text is escaped before it is rendered.
- **Abuse limits.**
  - Each browser gets its own conversation. Questions are limited per signed-in person and in total, and each question may make at most 20 model calls.
  - Pull requests are limited per browser and in total.
  - The demo passcode guards admin changes and pull requests, and 10 wrong tries in 15 minutes lock it.
  - The demo allows at most 8 people to be added through onboarding.
  - The container runs as a non-root user.
- **Saved chats.** Chats are stored per browser and person, so other visitors on the same persona never see them. They expire after 30 days through a Firestore TTL policy.
- **Public website.** It sends a strict Content-Security-Policy with no inline script or style. The work-email lookup only returns workspaces listed in `website/orgs.json`, so it can't be used as an open redirect, and it allows 20 lookups a minute per visitor. The site's service account has no roles.

## Tested attacks (17 Oct 2026)

| Attack | Stopped by |
|---|---|
| Planted prompt injection in a repository file | The agent treats file text as data (and layers 3, 4 and 6 still apply) |
| A PM asks for a code change | No write tool at the Ask level; a request is drafted instead |
| A designer edits `server.mjs` | The path allow-list |
| An edit via `public/css/../../lib/score.mjs` | The path check refuses `..` |
| A designer goes over budget | The gateway budget on the key |
| Someone asks the assistant for secrets | Secrets exist only in Secret Manager |
| A PM calls a model that isn't on her key | The gateway key (403) |
| A key tries to mint itself a new key | The key is limited to model routes (403) |
| A workspace calls Vertex AI directly | IAM: no Vertex AI role (403) |
| A bot PR touches `lib/score.mjs` | The CI allow-list check fails |

## Known limits

- The demo's personas stand in for directory groups: anyone who signs in can choose any persona. In production, the level comes from the person's group (Entra ID or Okta, through SAML and SCIM).
- The app holds the gateway's master key. A scoped admin key is on the roadmap.
- The app runs as one instance. Saved chats live in Firestore, but the conversation the assistant is working on is held in memory.
- On the demo repository, branch protection doesn't bind admins, so a token belonging to an admin could push to `main` directly. Turn on "Do not allow bypassing the above settings" for production.
- The citation checker proves where a citation points, not that the sentence is right.
