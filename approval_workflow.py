import time
import subprocess
import shutil
from pathlib import Path
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

VAULT = Path('/mnt/c/Users/dell/Documents/AI_Employee_Vault')
NEEDS_ACTION = VAULT / 'Needs_Action'
PENDING = VAULT / 'Pending_Approval'
APPROVED = VAULT / 'Approved'
REJECTED = VAULT / 'Rejected'
DONE = VAULT / 'Done'
LOG_FILE = VAULT / 'Logs' / 'approval.log'

TRIGGER_KEYWORDS = ['payment', 'invoice', 'transfer', 'urgent', 'contract', 'legal', 'bank']

def log(msg):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    entry = f"[{timestamp}] {msg}\n"
    with open(LOG_FILE, 'a') as f:
        f.write(entry)
    print(entry.strip())

def git_commit(message):
    subprocess.run(['git', '-C', str(VAULT), 'add', '-A'])
    subprocess.run(['git', '-C', str(VAULT), 'commit', '-m', message])
    subprocess.run(['git', '-C', str(VAULT), 'push'])

def needs_approval(filepath):
    content = filepath.read_text(encoding='utf-8').lower()
    return any(kw in content for kw in TRIGGER_KEYWORDS)

class NeedsActionHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory or event.src_path.endswith('.gitkeep'):
            return
        filepath = Path(event.src_path)
        filename = filepath.name
        if needs_approval(filepath):
            dest = PENDING / filename
            shutil.move(str(filepath), str(dest))
            log(f"MOVED TO PENDING_APPROVAL: {filename}")
            git_commit(f"approval: {filename} needs human review")
        else:
            log(f"AUTO-APPROVED: {filename} (no sensitive keywords)")

class ApprovedHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory or event.src_path.endswith('.gitkeep'):
            return
        filepath = Path(event.src_path)
        filename = filepath.name
        log(f"HUMAN APPROVED: {filename} - processing")
        dest = DONE / filename
        shutil.move(str(filepath), str(dest))
        log(f"MOVED TO DONE: {filename}")
        git_commit(f"done: approved item {filename}")

if __name__ == '__main__':
    log("=== Approval Workflow Started ===")
    touch_log = VAULT / 'Logs' / 'approval.log'
    touch_log.parent.mkdir(parents=True, exist_ok=True)

    observer = PollingObserver(timeout=2)
    na_handler = NeedsActionHandler()
    ap_handler = ApprovedHandler()
    observer.schedule(na_handler, str(NEEDS_ACTION), recursive=False)
    observer.schedule(ap_handler, str(APPROVED), recursive=False)
    observer.start()
    log("Watching Needs_Action/ and Approved/ folders")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("=== Approval Workflow Stopped ===")
        observer.stop()
    observer.join()
