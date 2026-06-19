import requests
from datetime import datetime


class AlertService:

    def __init__(self):
        pass

    # -------------------------
    # MAIN ENTRY POINT
    # -------------------------
    def send_alert(self, user, job):
        """
        Decide which channels to use per user
        """

        if user.get("email"):
            self.send_email(user["email"], job)

        if user.get("telegram"):
            self.send_telegram(user["telegram"], job)

        if user.get("webhook"):
            self.send_webhook(user["webhook"], job)

        self.log_alert(user, job)

    # -------------------------
    # EMAIL (mock for now)
    # -------------------------
    def send_email(self, email, job):
        print(f"[EMAIL] Sending to {email}: {job['title']} at {job['company']}")

        # Replace later with:
        # Resend / SendGrid / SMTP
        return True

    # -------------------------
    # TELEGRAM BOT
    # -------------------------
    def send_telegram(self, chat_id, job):
        BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

        message = f"""
🚨 New Job Match!

💼 {job['title']}
🏢 {job['company']}
📍 {job['location']}
🔗 {job['url']}
⭐ Score: {job.get('score', 0)}
"""

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

        requests.post(url, data={
            "chat_id": chat_id,
            "text": message
        })

    # -------------------------
    # WEBHOOK (for devs / pro users)
    # -------------------------
    def send_webhook(self, url, job):
        try:
            requests.post(url, json={
                "event": "job_match",
                "job": job,
                "timestamp": str(datetime.utcnow())
            })
        except Exception as e:
            print(f"[WEBHOOK ERROR] {e}")

    # -------------------------
    # LOGGING
    # -------------------------
    def log_alert(self, user, job):
        print(f"[ALERT SENT] {user.get('id')} → {job['title']}")
