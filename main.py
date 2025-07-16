import os
import requests
from flask import Flask, request
from datetime import datetime, timedelta
from google.cloud import firestore

app = Flask(__name__)
db = firestore.Client()

AD_ACCOUNT_ID = "1381598392129251"
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
CHAT_WEBHOOK = os.environ.get("CHAT_WEBHOOK")

COLLECTION_NAME = "meta_campaigns"

def send_alert(message):
    requests.post(CHAT_WEBHOOK, json={"text": message})

def is_within_working_hours():
    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return 10 <= now_ist.hour < 19

@app.route("/", methods=["GET"])
def monitor_campaigns():
    if not is_within_working_hours():
        return "Outside working hours", 200

    try:
        url = f"https://graph.facebook.com/v18.0/act_{AD_ACCOUNT_ID}/campaigns"
        params = {
            "access_token": ACCESS_TOKEN,
            "fields": "id,name,effective_status,daily_budget",
            "limit": 100
        }
        resp = requests.get(url, params=params)
        campaigns = resp.json().get("data", [])

        alerts = []
        for c in campaigns:
            cid = c["id"]
            name = c["name"]
            status = c.get("effective_status")
            budget = int(c.get("daily_budget", 0)) // 100  # ₹

            doc_ref = db.collection(COLLECTION_NAME).document(cid)
            stored = doc_ref.get().to_dict() or {}

            if not stored:
                doc_ref.set({"name": name, "budget": budget, "status": status})
                continue

            if stored["budget"] != budget or stored["status"] != status:
                alerts.append(f"⚠️ *{name}* — Status: *{status}* — ₹{budget}/day (was ₹{stored['budget']})")
                doc_ref.set({"name": name, "budget": budget, "status": status})

        if alerts:
            send_alert("\n".join(alerts))
        else:
            send_alert("✅ No budget/status changes found.")

        return "Checked", 200

    except Exception as e:
        send_alert(f"🚨 Meta Monitor Error:\n{str(e)}")
        return "Error", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
