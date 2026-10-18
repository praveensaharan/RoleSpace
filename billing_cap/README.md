# Project spending cap

A hard stop for the whole Google Cloud project. The project's billing budget sends its spend to the Pub/Sub topic `billing-cap`. A push subscription forwards each message to this Cloud Run service. When the month's spend reaches `STOP_AT`, the service unlinks the project's billing account. That stops every paid service at once: Cloud Run, the VMs, Cloud SQL and Vertex AI. Nothing restarts until someone links billing again in the console.

- **Trade-off.** Unlinking billing can delete resources, and turning things back on is manual. That is the price of a hard cap.
- **Delay.** Cost data reaches the budget hours late, so `STOP_AT` sits below the budget, for example ¥27,000 for a ¥30,000 budget.
- **Only our budget counts.** Messages whose `budgetId` isn't ours are ignored.
- **Dry run.** With `ARMED=false`, the service only logs what it would do.

```bash
PROJECT=your-project; REGION=us-central1; BA=$(gcloud billing projects describe $PROJECT --format='value(billingAccountName)' | cut -d/ -f2)
SA=billing-cap@$PROJECT.iam.gserviceaccount.com
gcloud services enable cloudbilling.googleapis.com pubsub.googleapis.com --project $PROJECT
gcloud iam service-accounts create billing-cap --project $PROJECT --display-name="Billing kill switch"
# Unlinking billing needs project rights and read access to the billing account
for r in roles/billing.projectManager roles/browser; do
  gcloud projects add-iam-policy-binding $PROJECT --member=serviceAccount:$SA --role=$r --condition=None
done
gcloud billing accounts add-iam-policy-binding $BA --member=serviceAccount:$SA --role=roles/billing.viewer

gcloud pubsub topics create billing-cap --project $PROJECT
gcloud billing budgets create --billing-account=$BA --display-name="Project hard cap" \
  --budget-amount=30000JPY --filter-projects=projects/$PROJECT --credit-types-treatment=exclude-all-credits \
  --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0 \
  --notifications-rule-pubsub-topic=projects/$PROJECT/topics/billing-cap
BUDGET_ID=$(gcloud billing budgets list --billing-account=$BA --format='value(name)' | head -1 | cut -d/ -f4)

gcloud run deploy billing-cap --source billing_cap --function handle --base-image python312 \
  --region $REGION --project $PROJECT --service-account $SA --no-allow-unauthenticated --ingress internal \
  --max-instances 1 --set-env-vars GOOGLE_CLOUD_PROJECT=$PROJECT,STOP_AT=27000,BUDGET_ID=$BUDGET_ID,ARMED=false
gcloud run services add-iam-policy-binding billing-cap --region $REGION --project $PROJECT \
  --member=serviceAccount:$SA --role=roles/run.invoker
URL=$(gcloud run services describe billing-cap --region $REGION --project $PROJECT --format='value(status.url)')
gcloud pubsub subscriptions create billing-cap-push --topic billing-cap --project $PROJECT \
  --push-endpoint=$URL/ --push-auth-service-account=$SA --ack-deadline=60
```

Watch the logs until a real spend report arrives ("Spend … is under the stop line"). Then arm the cap:

```bash
gcloud run services update billing-cap --region $REGION --project $PROJECT --update-env-vars ARMED=true
```
