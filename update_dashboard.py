from pathlib import Path
import time

VAULT = Path('/mnt/c/Users/dell/Documents/AI_Employee_Vault')

def count_files(folder):
    p = VAULT / folder
    return len([f for f in p.iterdir() if f.is_file() and f.name != '.gitkeep']) if p.exists() else 0

def update():
    inbox = count_files('Inbox')
    needs = count_files('Needs_Action')
    pending = count_files('Pending_Approval')
    approved = count_files('Approved')
    done = count_files('Done')
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

    content = f"""# AI Employee Dashboard
*Last Updated: {timestamp}*

## Status: 🟢 RUNNING

## Folder Counts
| Folder | Files |
|--------|-------|
| Inbox | {inbox} |
| Needs_Action | {needs} |
| Pending_Approval | {pending} |
| Approved | {approved} |
| Done | {done} |

## Active Watchers
- file_watcher.py → monitoring Inbox/
- gmail_watcher.py → monitoring Gmail
- approval_workflow.py → routing items

## Architecture
PERCEPTION (Watchers) → REASONING (Claude Code) → ACTION (MCP) → STORAGE (Vault)
"""
    (VAULT / 'Dashboard.md').write_text(content)
    print(f"[{timestamp}] Dashboard updated")

if __name__ == '__main__':
    while True:
        update()
        time.sleep(60)
