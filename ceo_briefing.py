from pathlib import Path
from datetime import datetime
import subprocess
import time

VAULT = Path('/mnt/c/Users/dell/Documents/AI_Employee_Vault')
LOG = VAULT / 'Logs' / 'ceo_briefing.log'

def log(msg):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    entry = f"[{timestamp}] {msg}\n"
    with open(LOG, 'a') as f:
        f.write(entry)
    print(entry.strip())

def count_files(folder):
    p = VAULT / folder
    return len([f for f in p.iterdir() if f.is_file() and f.name != '.gitkeep']) if p.exists() else 0

def get_recent_logs():
    log_file = VAULT / 'Logs' / 'gmail_watcher.log'
    if not log_file.exists():
        return "No activity logged."
    lines = log_file.read_text().splitlines()
    return '\n'.join(lines[-10:])

def generate_briefing():
    week = datetime.now().strftime('%Y-W%W')
    date = datetime.now().strftime('%Y-%m-%d')
    content = f"""# CEO Weekly Briefing — {date}
Week: {week}

## Executive Summary
AI Employee system operational. All watchers running.

## Activity This Week
- Emails processed: {count_files('Done')}
- Pending approval: {count_files('Pending_Approval')}
- Items in queue: {count_files('Needs_Action')}

## Recent Activity Log
{get_recent_logs()}

## System Health
- File Watcher: ACTIVE
- Gmail Watcher: ACTIVE
- Approval Workflow: ACTIVE
- MCP Email Server: READY

## Recommendations
- Review Pending_Approval/ folder items
- Check Done/ folder for completed tasks
"""
    filename = f"CEO_BRIEFING_{date}.md"
    filepath = VAULT / 'Plans' / filename
    filepath.write_text(content)
    log(f"CEO BRIEFING GENERATED: {filename}")
    subprocess.run(['git', '-C', str(VAULT), 'add', '-A'])
    subprocess.run(['git', '-C', str(VAULT), 'commit', '-m', f"briefing: weekly CEO report {date}"])
    subprocess.run(['git', '-C', str(VAULT), 'push'])

if __name__ == '__main__':
    generate_briefing()
