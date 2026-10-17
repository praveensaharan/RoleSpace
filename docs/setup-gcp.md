# Deploying RoleSpace on Google Cloud

This guide sets up the same system that runs at rolespace.duckdns.org. Replace `PROJECT` and `REGION` with your own values. All commands run in Cloud Shell or on any machine where `gcloud` is signed in as a project owner.

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
for r in roles/aiplatform.user roles/cloudsql.client roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding $PROJECT \
    --member="serviceAccount:rs-gateway@$PROJECT.iam.gserviceaccount.com" --role="$r"
done
```

Store the secrets the gateway reads:
- `litellm-master-key`
- `litellm-salt-key`
- `litellm-database-url`, in the form `postgresql://litellm:PASSWORD@localhost/litellm?host=/cloudsql/PROJECT:REGION:rs-sql`

Then deploy [`gateway/`](../gateway):
- Use `--service-account rs-gateway@…` and `--add-cloudsql-instances $PROJECT:$REGION:rs-sql`.
- Set `LITELLM_MASTER_KEY`, `LITELLM_SALT_KEY` and `DATABASE_URL` from those secrets, and `GOOGLE_CLOUD_PROJECT=$PROJECT`.
- Use `--no-allow-unauthenticated`, 1 CPU, 2 GiB, one instance, and keep the CPU always allocated.

Callers send a Google ID token in `X-Serverless-Authorization` and the LiteLLM key in `Authorization`.

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
for r in roles/datastore.user roles/secretmanager.secretAccessor roles/logging.logWriter roles/compute.viewer; do
  gcloud projects add-iam-policy-binding $PROJECT \
    --member="serviceAccount:rolespace-run@$PROJECT.iam.gserviceaccount.com" --role="$r"
done
gcloud run services add-iam-policy-binding rs-gateway --region=$REGION \
  --member="serviceAccount:rolespace-run@$PROJECT.iam.gserviceaccount.com" --role=roles/run.invoker
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

`role.yaml` lists every model in its `models:` catalog. Models marked `available` need one step before an admin switches them on:
- **Claude on Vertex AI:**
  1. Enable the model in Vertex AI Model Garden.
  2. Uncomment `claude-opus` in `gateway/config.yaml` and redeploy the gateway.
  3. Set its status to `enabled` and add it to a level's `models`.
  4. Run `gateway/provision_keys.py`.
- **OpenAI:**
  1. Store the customer's key as the secret `openai-api-key` and mount it on the gateway as `OPENAI_API_KEY`.
  2. Uncomment `openai-codex` in `gateway/config.yaml`, with the model id.
  3. Then follow steps 3 and 4 above.

Re-run the evaluation with a model before enabling it for a level. See [enterprise-design.md](enterprise-design.md) for the full design.

## Evaluate

```bash
RS_COLLECTION_PREFIX=eval_ uvicorn main:app --port 8090 &   # keeps test events out of the live audit log
python eval/run_eval.py http://localhost:8090
```
