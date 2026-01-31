import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from config import Config

# Simple in-memory rate limiter
# Dictionary to store last alert time for different keys
_last_alert_time = {}
ALERT_COOLDOWN_MINUTES = 60

def send_admin_alert(subject, body):
    """
    Sends an email to the admin.
    Includes rate limiting to avoid spamming (one alert per hour per subject).
    """
    global _last_alert_time
    
    # Check rate limit
    now = datetime.now()
    if subject in _last_alert_time:
        last_time = _last_alert_time[subject]
        if now - last_time < timedelta(minutes=ALERT_COOLDOWN_MINUTES):
            print(f"Skipping email alert '{subject}' (Rate limited)")
            return False
            
    # Update last time
    _last_alert_time[subject] = now
    
    if not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD:
        print(f"⚠️ Email config missing. Would have sent: [Subject: {subject}] {body}")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = Config.MAIL_DEFAULT_SENDER
        msg['To'] = Config.ADMIN_EMAIL
        msg['Subject'] = f"[UOH Speech Alert] {subject}"

        msg.attach(MIMEText(body, 'plain'))

        # Connect to SMTP server
        server = smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT)
        if Config.MAIL_USE_TLS:
            server.starttls()
            
        server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(Config.MAIL_DEFAULT_SENDER, Config.ADMIN_EMAIL, text)
        server.quit()
        
        print(f"📧 Admin alert sent: {subject}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email alert: {e}")
        return False
