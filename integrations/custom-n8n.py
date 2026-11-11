#!/usr/bin/env python3
"""
Custom Wazuh-to-n8n SOAR Integration Bridge
Author: Dinujaya Thamara (dinu-bot)
Description: Forwards high-severity Wazuh alerts (Level >= 10) from
             /var/ossec/logs/alerts/alerts.json to the n8n SOAR webhook.
"""
import json
import sys
import urllib.request
import urllib.error

def main():
    if len(sys.argv) < 4:
        sys.exit(1)

    alert_file_path = sys.argv[1]
    webhook_url = sys.argv[3]

    try:
        with open(alert_file_path, "r", encoding="utf-8") as f:
            alert_json = json.load(f)
    except Exception as e:
        sys.stderr.write(f"[custom-n8n] Failed to read alert file: {e}\n")
        sys.exit(1)

    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(alert_json).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Wazuh-SOAR-Bridge/1.0"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            sys.stdout.write(f"[custom-n8n] Dispatched alert {alert_json.get('id')} -> HTTP {resp.status}\n")
    except urllib.error.URLError as e:
        sys.stderr.write(f"[custom-n8n] Webhook dispatch error: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
