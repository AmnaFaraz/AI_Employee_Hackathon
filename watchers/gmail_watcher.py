from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime
from pathlib import Path
import subprocess
import time
import re

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
VAULT = Path('/mnt/c/Users/dell/Documents/AI_Employee_Vault')
NEEDS_ACTION = VAULT / 'Needs_Action'
LOG_FILE = VAULT / 'Logs' / 'gmail_watcher.log'
CREDS_FILE = VAULT / 'watchers' / 'credentials.json'
TOKEN_FILE = VAULT / 'watchers' / 'token.json'

def log(msg):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    entry = f"[{timestamp}] {msg}\n"
    with open(LOG_FILE, 'a') as f:
        f.write(entry)
    print(entry.strip())

def safe_filename(text, maxlen=40):
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s]+', '-', text).strip('-').lower()
    return text[:maxlen] if text else 'no-subject'

def git_commit(message):
    subprocess.run(['git', '-C', str(VAULT), 'add', '-A'])
    subprocess.run(['git', '-C', str(VAULT), 'commit', '-m', message])
    subprocess.run(['git', '-C', str(VAULT), 'push'])

def invoke_claude(filename, subject):
    prompt = f"""You are an AI Employee. New email arrived: '{subject}'.
File saved at Needs_Action/{filename}.

Follow .claude/skills/email-processing.md:
1. Read the email file
2. Determine priority: high/normal/low
3. Check if approval needed per .claude/skills/approval-workflow.md
4. If sensitive: move to Pending_Approval/
5. Create PLAN_{filename} in Plans/ with action steps
6. Update Dashboard.md
7. Log actions to Logs/vault.log"""

    result = subprocess.run(
        ['claude', '-p', prompt, '--cwd', str(VAULT)],
        capture_output=True, text=True, timeout=120
    )
    log(f"CLAUDE REASONED: {filename}")
    return result.stdout

def get_credentials():
    if TOKEN_FILE.exists():
        return Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json())
    return creds

def main():
    log("=== Gmail Watcher + Claude Started ===")
    NEEDS_ACTION.mkdir(parents=True, exist_ok=True)
    creds = get_credentials()
    service = build('gmail', 'v1', credentials=creds)
    processed = set()

    while True:
        try:
            results = service.users().messages().list(
                userId='me', q='is:unread', maxResults=10
            ).execute()
            messages = results.get('messages', [])

            for msg_meta in messages:
                if msg_meta['id'] in processed:
                    continue
                msg = service.users().messages().get(
                    userId='me', id=msg_meta['id']
                ).execute()
                headers = {h['name']: h['value'] for h in msg['payload']['headers']}
                subject = headers.get('Subject', 'No Subject')
                sender = headers.get('From', 'Unknown')
                slug = safe_filename(subject)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

                content = f"""---
type: email
from: {sender}
subject: {subject}
received: {datetime.now().isoformat()}
priority: normal
status: pending
---

## Email Content
{msg.get('snippet', '')}

## Actions Required
- [ ] Read and respond
- [ ] Move to Done when complete
"""
                filename = f"EMAIL_{timestamp}_{slug}.md"
                (NEEDS_ACTION / filename).write_text(content, encoding='utf-8')
                processed.add(msg_meta['id'])
                log(f"NEW EMAIL SAVED: {filename}")
                invoke_claude(filename, subject)
                git_commit(f"email: claude processed - {subject[:40]}")

            time.sleep(120)

        except Exception as e:
            log(f"ERROR: {e}")
            time.sleep(120)

if __name__ == '__main__':
    main()
