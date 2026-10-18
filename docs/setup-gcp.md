# Deploying RoleSpace on Google Cloud

This guide sets up the same system that runs at rolespace.duckdns.org (website) and rolespace.duckdns.org/rolespace-ent/ (app). Replace `PROJECT` and `REGION` with your own values. All commands run in Cloud Shell or on any machine where `gcloud` is signed in as a project owner.

```bash
PROJECT=your-project-id
REGION=us-central1
gcloud config set project $PROJECT
gcloud services enable run.googleapis.com aiplatform.googleapis.com firestore.googleapis.com \
  secretmanager.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  compute.googleapis.com iap.googleapis.com sqladmin.googleapis.com
gcloud firestore databases create --location=$REGION
```

A new project's default compute service account builds the containers, and it may need `roles/cloudbuild.builds.builder` before `gcloud run deploy --source` works.

## 1. Model gateway (LiteLLM on Cloud Run)

The gateway is the only identity allowed to call Gemini. Every other caller goes through it with a person's own key.

```bash
# Database for keys, budgets and spend
gcloud sql instances create rs-sql --database-version=POSTGRES_16 --edition=ENTERPRISE \
  --tier=db-f1-micro --region=$REGION
gcloud sql databases create litellm --instance=rs-sql
gcloud sql users create litellm --instance=rs-sql --password="$DB_PASSWORD"

# The gateway's service account: the only one with the Vertex AI role
gcloud iam service-accounts create rs-gateway
for r in roles/aiplatform.user roles/cloudsql.client; do
  gcloud projects add-iam-policy-binding $PROJECT \
    --member="serviceAccount:rs-gateway@$PROJECT.iam.gserviceaccount.com" --role="$r"
done
```

Store the secrets the gateway reads:
- `litellm-master-key`
- `litellm-salt-key`
- `litellm-database-url`, in the form `postgresql://litellm:PASSWORD@localhost/litellm?host=/cloudsql/PROJECT:REGION:rs-sql`

Grant the gateway those three secrets only, one binding per secret, not Secret Manager access for the whole project:

```bash
for s in litellm-master-key litellm-salt-key litellm-database-url; do
  gcloud secrets add-iam-policy-binding $s --role=roles/secretmanager.secretAccessor \
    --member="serviceAccount:rs-gateway@$PROJECT.iam.gserviceaccount.com"
done
```

Then deploy [`gateway/`](../gateway):
- Use `--service-account rs-gateway@…` and `--add-cloudsql-instances $PROJECT:$REGION:rs-sql`.
- Set `LITELLM_MASTER_KEY`, `LITELLM_SALT_KEY` and `DATABASE_URL` from those secrets, and `GOOGLE_CLOUD_PROJECT=$PROJECT`.
- Use `--no-allow-unauthenticated`, 1 CPU, 2 GiB, one instance, and keep the CPU always allocated.

Callers send a Google ID token in `X-Serverless-Authorization` and the LiteLLM key in `Authorization`.

`gateway/config.yaml` also sets a hard ceiling for all AI spend together (`max_budget` with `budget_duration: 30d`). Past it, the gateway refuses every call, whatever each person's budget says. Only a gateway redeploy changes it.

Give each person a key, with their level's models and budget, limited to model routes:

```bash
python3 gateway/provision_keys.py     # reads role.yaml; stores each key as gw-key-<person>
```

## 2. Network and the Coder workspace VM

```bash
# Private subnet: outbound through Cloud NAT, inbound only from IAP
gcloud compute networks create rs-vpc --subnet-mode=custom
gcloud compute networks subnets create rs-private --network=rs-vpc --region=$REGION \
  --range=10.1.2.0/24 --enable-private-ip-google-access
gcloud compute routers create rs-router --network=rs-vpc --region=$REGION
gcloud compute routers nats create rs-nat --router=rs-router --region=$REGION \
  --auto-allocate-nat-external-ips --nat-all-subnet-ip-ranges
gcloud compute firewall-rules create rs-allow-iap --network=rs-vpc \
  --allow=tcp:22,tcp:3000 --source-ranges=35.235.240.0/20

# The VM: no public IP, and a service account with no Vertex AI role
gcloud iam service-accounts create rs-workspace
gcloud compute instances create coder-vm --zone=$REGION-a --machine-type=e2-standard-4 \
  --subnet=rs-private --no-address --boot-disk-size=50GB \
  --image-family=ubuntu-2404-lts-amd64 --image-project=ubuntu-os-cloud \
  --service-account=rs-workspace@$PROJECT.iam.gserviceaccount.com --scopes=cloud-platform
gcloud run services add-iam-policy-binding rs-gateway --region=$REGION \
  --member="serviceAccount:rs-workspace@$PROJECT.iam.gserviceaccount.com" --role=roles/run.invoker
```

Next, set up the VM:
1. Copy [`coder/gateway-relay.py`](../coder/gateway-relay.py) to `/tmp` on the VM.
2. Run [`coder/setup-vm.sh`](../coder/setup-vm.sh) as root. It installs Docker, a checksum-verified Coder and the relay.
3. Build the workspace image from [`coder/image/`](../coder/image).
4. Push the template in [`coder/template/`](../coder/template).
5. Run [`coder/sync_build_keys.sh`](../coder/sync_build_keys.sh), so that only Build-level people get a workspace.

Open Coder with [`coder/tunnel.sh`](../coder/tunnel.sh), which runs an IAP tunnel to `localhost:3000`.

## 3. The RoleSpace app

```bash
gcloud iam service-accounts create rolespace-run
SA=serviceAccount:rolespace-run@$PROJECT.iam.gserviceaccount.com
for r in roles/datastore.user roles/logging.logWriter roles/compute.viewer; do
  gcloud projects add-iam-policy-binding $PROJECT --member=$SA --role="$r"
done
gcloud run services add-iam-policy-binding rs-gateway --region=$REGION --member=$SA --role=roles/run.invoker

# Secrets: one binding per secret the app reads, plus the people's own keys (gw-key-*)
for s in litellm-master-key github-token demo-admin-passcode; do
  gcloud secrets add-iam-policy-binding $s --member=$SA --role=roles/secretmanager.secretAccessor
done
PROJECT_NUMBER=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
gcloud projects add-iam-policy-binding $PROJECT --member=$SA --role=roles/secretmanager.secretAccessor \
  --condition="expression=resource.name.startsWith('projects/$PROJECT_NUMBER/secrets/gw-key-'),title=gw-key secrets only"
```

The app also needs these secrets:
- `github-token`: a fine-grained token for the demo repository only, with Contents and Pull requests set to read/write. Type it with `read -s`, never paste it.
- `demo-admin-passcode`: optional. When it exists, admin changes and pull requests ask for it.

Then deploy with [`deploy.sh`](../deploy.sh). It pins the demo codebase into `repo/` first. Set `GOOGLE_CLOUD_PROJECT`, `GATEWAY_URL` and `GITHUB_REPO` in it for your project.

On the demo repository, add the [`designer-allowlist` workflow](https://github.com/praveensaharan/firstround-demo/blob/main/.github/workflows/designer-allowlist.yml) and turn on branch protection: one review and that check, both required.

## 4. Google sign-in for the app

To put the app behind Google sign-in:
1. Create an external HTTPS load balancer with a serverless NEG pointing at the `rolespace` service.
2. Set the service's ingress to `internal-and-cloud-load-balancing`.
3. Turn on IAP for the backend service.
4. Grant `roles/iap.httpsResourceAccessor` to the people or groups who should get in.

If your project isn't in a Google Cloud organization, or users sign in with accounts from outside it, IAP needs a **custom OAuth client**:
1. In **Google Auth Platform → Branding**, set the audience to **External**, then publish the app or add test users.
2. In **IAP → Settings**, choose **Custom OAuth** and **Auto Generate Credentials**.

## 5. The public website (optional)

[`website/`](../website) is the public product site: static pages plus one lookup that turns a work email into its organization's workspace. It runs as its own Cloud Run service with a service account that has no roles at all.

```bash
gcloud iam service-accounts create rolespace-site     # no roles: the site reads nothing in the project
LB_IP=YOUR_LOAD_BALANCER_IP ./website/deploy.sh
```

- Map your company's email domains to workspace URLs in [`website/orgs.json`](../website/orgs.json). The lookup only ever returns URLs listed there.
- `TRUSTED_PROXIES` lists the load balancer's IP and Google's front-end ranges. The rate limit (20 lookups a minute) then counts each visitor, not the load balancer.

To serve the website at your domain's root and the app under `/rolespace-ent/` on the same load balancer, add a second backend without IAP. Then route by path:
- `/` goes to the website.
- `/rolespace-ent/` goes to the app, rewritten to `/`.
- The app's own `/api/`, `/static/` and IAP's `/_gcp_gatekeeper/` and `/_gcp_iap/` paths go to the app.
- `/api/org` stays with the website.

`www.` can be redirected to the root, or served as its own host.

```bash
gcloud compute network-endpoint-groups create rolespace-site-neg --region=$REGION \
  --network-endpoint-type=serverless --cloud-run-service=rolespace-site
gcloud compute backend-services create rolespace-site-backend --global --load-balancing-scheme=EXTERNAL_MANAGED
gcloud compute backend-services add-backend rolespace-site-backend --global \
  --network-endpoint-group=rolespace-site-neg --network-endpoint-group-region=$REGION
```

Then apply the routing in [`lb/urlmap.yaml`](../lb/urlmap.yaml) with [`lb/apply_urlmap.sh`](../lb/apply_urlmap.sh). It fills in your project and domain, validates the map, saves the previous one for a rollback and imports the new one:

```bash
DOMAIN=YOUR_DOMAIN ./lb/apply_urlmap.sh --check   # validate only
DOMAIN=YOUR_DOMAIN ./lb/apply_urlmap.sh
```

Set the website's workspace URL in `website/orgs.json` to `https://YOUR_DOMAIN/rolespace-ent/`. A managed certificate goes active 15–60 minutes after its domain points at the load balancer.

## 6. A hard spending cap (optional)

[`billing_cap/`](../billing_cap) stops the whole project when the month's spend nears a set amount. The billing budget publishes its spend to Pub/Sub, and a small Cloud Run service unlinks billing at the stop line. It starts in dry-run, logging what it would do. Its [README](../billing_cap/README.md) has the commands, and the trade-off: unlinking billing stops everything in the project, and turning it back on is manual.

## Onboarding new people

Govern → People → **Add person** creates the person's gateway key and stores it as the secret `gw-key-<id>`. The app's service account can read secrets but not create them, so grant two narrow custom roles:
- **Create secrets.** This gives no access to existing ones.
- **Add versions,** only to secrets whose names start with `gw-key-`. The app then can't overwrite `github-token` or `litellm-master-key`.

```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
SA=serviceAccount:rolespace-run@$PROJECT.iam.gserviceaccount.com
gcloud iam roles create rolespaceSecretCreator --project=$PROJECT \
  --title="RoleSpace: create secrets" --permissions=secretmanager.secrets.create
gcloud projects add-iam-policy-binding $PROJECT --member=$SA \
  --role=projects/$PROJECT/roles/rolespaceSecretCreator --condition=None
gcloud iam roles create rolespaceKeyWriter --project=$PROJECT \
  --title="RoleSpace: store gateway keys" --permissions=secretmanager.versions.add
gcloud projects add-iam-policy-binding $PROJECT --member=$SA \
  --role=projects/$PROJECT/roles/rolespaceKeyWriter \
  --condition="expression=resource.name.startsWith('projects/$PROJECT_NUMBER/secrets/gw-key-'),title=gw-key secrets only"
```

Without these roles, **Add person** stops at its first step, creates nothing, and says which grant is missing.

After you change `rpm_limit` or `tpm_limit` in `role.yaml`, run `python gateway/provision_keys.py` again so existing keys get the new limits.

## More models

`role.yaml` lists every model in its `models:` catalog.
- **Live today:** Gemini 3.8 Flash and 3.1 Pro, plus Kimi K2 and Qwen3 Coder from Vertex AI Model Garden.
- **Served but switched off:** DeepSeek V3.2. An admin can switch it on per level in Govern → Policy, then **Push to keys**.
- **Pinned prices:** `gateway/config.yaml` sets a per-token price for each Model Garden partner model, because LiteLLM 1.105.1 would otherwise log their spend as $0.

Models that need a one-time step first:
- **Claude on Vertex AI:**
  1. Enable the model in Vertex AI Model Garden and make sure the project has quota.
  2. Uncomment `claude-sonnet` in `gateway/config.yaml` and redeploy the gateway.
  3. Add it to the `models:` catalog in `role.yaml`, then switch it on per level in Govern → Policy.
- **OpenAI:**
  1. Store the customer's key as the secret `openai-api-key` and mount it on the gateway as `OPENAI_API_KEY`.
  2. Uncomment `openai-codex` in `gateway/config.yaml`, with the model id.
  3. Then follow step 3 above.

Re-run the evaluation with a model before enabling it for a level. See [enterprise-design.md](enterprise-design.md) for the full design.

## Evaluate

```bash
RS_COLLECTION_PREFIX=eval_ uvicorn main:app --port 8090 &   # keeps test events out of the live audit log
python eval/run_eval.py http://localhost:8090
```
