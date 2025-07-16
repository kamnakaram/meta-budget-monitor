import os
import requests
from datetime import datetime, timedelta
from flask import Flask, request

app = Flask(__name__)

# Replace with your Meta Ad Account ID
AD_ACCOUNT_ID = "1381598392129251"

# Google Chat Webhook
CHAT_WEBHOOK = "https://chat.googleapis.com/v1/spaces/AAAAivwuEaY/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=tEFGbnqCvsOGnBQ8tV489CcZrFX2yrp6GQ82h-6bztM="

# Meta Access Token (you’ll inject this as a secret in Cloud later)
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")

def send_alert(message):
    requests.post(CHAT_WEBHOOK, json={"text": message})

def is_within_working_hours():
    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return 10 <= now_ist.hour < 19

@app.route("/", methods=["GET"])
def monitor_budget():
    if not is_within_working_hours():
        return "Outside working hours", 200

    try:
        campaigns_url = f"https://graph.facebook.com/v18.0/act_{AD_ACCOUNT_ID}/campaigns"
        campaigns_resp = requests.get(campaigns_url, params={
            "access_token": ACCESS_TOKEN,
            "fields": "name,status,daily_budget,effective_status,lifetime_spend",
            "limit": 100
        })
        campaigns_resp.raise_for_status()
        campaigns = campaigns_resp.json().get("data", [])

        alerts = []

        for c in campaigns:
            name = c["name"]
            if "PMAX" in name.upper() or "DEMAND GEN" in name.upper():
                daily_budget = int(c.get("daily_budget", 0)) / 100  # Convert to rupees
                status = c.get("effective_status")
                spend = float(c.get("lifetime_spend", 0)) / 100  # Convert to rupees

                if daily_budget == 0 or status != "ACTIVE":
                    alerts.append(f"⚠️ Campaign *{name}* is *{status}* with ₹{daily_budget} budget")
                else:
                    alerts.append(f"✅ *{name}* — ₹{daily_budget:.0f}/day — Total Spend ₹{spend:.0f}")

        if alerts:
            send_alert("\n".join(alerts))
        else:
            send_alert("✅ No PMAX or Demand Gen campaigns found.")

        return "Checked", 200

    except Exception as e:
        send_alert(f"🚨 Meta Budget Monitor Failed:\n{str(e)}")
        return "Error", 500
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

