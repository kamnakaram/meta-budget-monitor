import os
import requests
from datetime import datetime, timedelta
from flask import Flask
from google.cloud import firestore

app = Flask(__name__)

AD_ACCOUNT_ID = "1381598392129251"
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
CHAT_WEBHOOK = os.environ.get("CHAT_WEBHOOK")
FIRESTORE_PROJECT_ID = os.environ.get("GCP_PROJECT")

db = firestore.Client(project=FIRESTORE_PROJECT_ID)

def send_alert(message):
    requests.post(CHAT_WEBHOOK, json={"text": message})

def is_within_working_hours():
    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return 10 <= now_ist.hour < 19

def get_existing_budgets():
    doc_ref = db.collection("adset_budgets").document("latest")
    doc = doc_ref.get()
    return doc.to_dict() if doc.exists else {}

def update_budgets(new_data):
    db.collection("adset_budgets").document("latest").set(new_data)

@app.route("/", methods=["GET"])
def monitor():
    if not is_within_working_hours():
        return "Outside working hours", 200

    try:
        url = f"https://graph.facebook.com/v18.0/act_{AD_ACCOUNT_ID}/adsets"
        response = requests.get(url, params={
            "access_token": ACCESS_TOKEN,
            "fields": "name,daily_budget,effective_status",
            "limit": 100
        })
        response.raise_for_status()
        adsets = response.json().get("data", [])

        old_data = get_existing_budgets()
        new_data = {}
        changes = []

        for adset in adsets:
            adset_id = adset.get("id")
            name = adset.get("name")
            budget = int(adset.get("daily_budget", 0)) / 100
            status = adset.get("effective_status")

            new_data[adset_id] = budget

            if adset_id not in old_data:
                changes.append(f"🆕 *{name}* added with ₹{budget:.0f}/day")
            elif old_data[adset_id] != budget:
                changes.append(f"✏️ *{name}* budget changed: ₹{old_data[adset_id]:.0f} → ₹{budget:.0f}")

        if changes:
            send_alert("🔔 *Meta Ad Set Budget Updates:*\n" + "\n".join(changes))
        else:
            send_alert("✅ No Meta ad set budget changes detected.")

        update_budgets(new_data)
        return "Checked", 200

    except Exception as e:
        send_alert(f"🚨 Budget Monitor Error:\n{str(e)}")
        return "Error", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
