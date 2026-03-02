import time
import subprocess
from pathlib import Path

VAULT = Path('/mnt/c/Users/dell/Documents/AI_Employee_Vault')
LOG = VAULT / 'Logs' / 'ralph.log'

def log(msg):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    entry = f"[{timestamp}] {msg}\n"
    with open(LOG, 'a') as f:
        f.write(entry)
    print(entry.strip())

def git_commit(msg):
    subprocess.run(['git', '-C', str(VAULT), 'add', '-A'])
    subprocess.run(['git', '-C', str(VAULT), 'commit', '-m', msg])
    subprocess.run(['git', '-C', str(VAULT), 'push'])

def scan_and_act():
    needs = VAULT / 'Needs_Action'
    if not needs.exists():
        return
    files = [f for f in needs.iterdir() if f.is_file() and f.name != '.gitkeep']
    for filepath in files:
        content = filepath.read_text(encoding='utf-8').lower()
        filename = filepath.name
        done = VAULT / 'Done' / filename
        if 'action required: no' in content or 'no action' in content:
            filepath.rename(done)
            log(f"AUTO-DONE (no action needed): {filename}")
            git_commit(f"ralph: auto-archived {filename}")
        else:
            log(f"PENDING HUMAN REVIEW: {filename}")

if __name__ == '__main__':
    log("=== Ralph Wiggum Autonomous Loop Started ===")
    while True:
        scan_and_act()
        time.sleep(300)
