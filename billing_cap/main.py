"""Hard spending cap for the whole Google Cloud project.

The project's billing budget publishes its spend to the Pub/Sub topic `billing-cap` several
times a day; a push subscription sends each message here. When the month's spend reaches
STOP_AT, this unlinks the project's billing account, which stops every paid service in the
project at once (Cloud Run, VMs, Cloud SQL, Vertex AI). Nothing restarts until a person links
billing again in the console.

Cost data reaches the budget hours after it is spent, so STOP_AT sits below the budget to
leave room for that delay. Only messages from our own budget count (budgetId attribute).
ARMED=false logs what it would do without doing it.
"""

import base64
import json
import os

import functions_framework
from google.cloud import billing_v1

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
STOP_AT = float(os.environ["STOP_AT"])
BUDGET_ID = os.environ["BUDGET_ID"]
ARMED = os.environ.get("ARMED") == "true"


def log(severity: str, message: str, **fields) -> None:
    # Cloud Run turns one JSON line on stdout into a structured log entry.
    print(json.dumps({"severity": severity, "message": message, **fields}), flush=True)


@functions_framework.http
def handle(request):
    msg = (request.get_json(silent=True) or {}).get("message") or {}
    attrs = msg.get("attributes") or {}
    if attrs.get("budgetId") != BUDGET_ID:
        log("WARNING", "Ignored a message that isn't from the project's budget", attributes=attrs)
        return "", 204
    data = json.loads(base64.b64decode(msg.get("data") or "e30=") or b"{}")
    cost, currency = float(data.get("costAmount", 0)), data.get("currencyCode", "")
    if cost < STOP_AT:
        log("INFO", f"Spend {cost:,.0f} {currency} is under the stop line {STOP_AT:,.0f}",
            cost=cost, stop_at=STOP_AT, period_start=data.get("costIntervalStart"))
        return "", 204

    client = billing_v1.CloudBillingClient()
    name = f"projects/{PROJECT}"
    if not client.get_project_billing_info(name=name).billing_enabled:
        log("INFO", "Spend is over the stop line and billing is already off", cost=cost)
        return "", 204
    if not ARMED:
        log("CRITICAL", f"Would unlink billing now (not armed): spend {cost:,.0f} {currency}", cost=cost)
        return "", 204
    client.update_project_billing_info(
        name=name, project_billing_info=billing_v1.ProjectBillingInfo(billing_account_name=""))
    log("CRITICAL", f"Billing unlinked: spend {cost:,.0f} {currency} reached {STOP_AT:,.0f}. "
                    "Every paid service in the project has stopped.", cost=cost)
    return "", 204
