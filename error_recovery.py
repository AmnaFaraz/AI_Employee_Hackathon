import subprocess
import time
from pathlib import Path

VAULT = Path('/mnt/c/Users/dell/Documents/AI_Employee_Vault')
LOG = VAULT / 'Logs' / 'error_recovery.log'

WATCHERS = {
    'file_watcher': {
        'script': 'file_watcher.py',
        'pid_file': 'Logs/file_watcher.pid'
    },
    'gmail_watcher': {
        'script': 'watchers/gmail_watcher.py',
        'pid_file': 'Logs/gmail_watcher.pid'
    },
    'approval_workflow': {
        'script': 'approval_workflow.py',
        'pid_file': 'Logs/approval.pid'
    }
}

def log(msg):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    entry = f"[{timestamp}] {msg}\n"
    with open(LOG, 'a') as f:
        f.write(entry)
    print(entry.strip())

def is_running(pid_file):
    pf = VAULT / pid_file
    if not pf.exists():
        return False
    pid = int(pf.read_text().strip())
    try:
        result = subprocess.run(['kill', '-0', str(pid)], capture_output=True)
        return result.returncode == 0
    except:
        return False

def restart(name, script):
    log(f"RESTARTING: {name}")
    venv_python = str(VAULT / 'venv' / 'bin' / 'python')
    proc = subprocess.Popen([venv_python, str(VAULT / script)])
    pid_file = VAULT / WATCHERS[name]['pid_file']
    pid_file.write_text(str(proc.pid))
    log(f"RESTARTED: {name} PID={proc.pid}")

if __name__ == '__main__':
    log("=== Error Recovery Monitor Started ===")
    while True:
        for name, config in WATCHERS.items():
            if not is_running(config['pid_file']):
                log(f"DOWN: {name} — triggering restart")
                restart(name, config['script'])
        time.sleep(30)
