import json
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import time

VAULT = Path('/mnt/c/Users/dell/Documents/AI_Employee_Vault')
LOG_FILE = VAULT / 'Logs' / 'mcp_email.log'

def log(msg):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    entry = f"[{timestamp}] {msg}\n"
    with open(LOG_FILE, 'a') as f:
        f.write(entry)
    print(entry.strip())

def send_email(to, subject, body, gmail_user, gmail_app_password):
    msg = MIMEMultipart()
    msg['From'] = gmail_user
    msg['To'] = to
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(gmail_user, gmail_app_password)
        server.sendmail(gmail_user, to, msg.as_string())
    log(f"EMAIL SENT: to={to} subject={subject}")
    return {"status": "sent", "to": to, "subject": subject}

def handle_request(request):
    method = request.get('method')
    params = request.get('params', {})
    if method == 'send_email':
        return send_email(
            params['to'],
            params['subject'],
            params['body'],
            params['gmail_user'],
            params['gmail_app_password']
        )
    return {"error": "unknown method"}

if __name__ == '__main__':
    log("=== MCP Email Server Started ===")
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            result = handle_request(request)
            print(json.dumps(result))
            sys.stdout.flush()
        except Exception as e:
            log(f"ERROR: {e}")
            print(json.dumps({"error": str(e)}))
            sys.stdout.flush()
