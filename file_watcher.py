import time
import subprocess
from pathlib import Path
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

VAULT = Path('/mnt/c/Users/dell/Documents/AI_Employee_Vault')
INBOX = VAULT / 'Inbox'
LOG_FILE = VAULT / 'Logs' / 'watcher.log'

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

def invoke_claude(filename):
    prompt = f"""You are an AI Employee. A new file '{filename}' arrived in Inbox/.

Read the file content from /Inbox/{filename}.
Follow the skills in .claude/skills/vault-management.md.
Decide: should this go to Needs_Action/ or Done/?
Create a PLAN_{filename} in Plans/ with your reasoning.
Update Dashboard.md with current status.
Move the file to correct folder.
Log all actions to Logs/vault.log."""

    result = subprocess.run(
        ['claude', '-p', prompt, '--cwd', str(VAULT)],
        capture_output=True, text=True, timeout=120
    )
    log(f"CLAUDE PROCESSED: {filename}")
    log(f"CLAUDE OUTPUT: {result.stdout[:200]}")
    return result.stdout

class InboxHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory or event.src_path.endswith('.gitkeep'):
            return
        filename = Path(event.src_path).name
        log(f"NEW FILE DETECTED: {filename}")
        invoke_claude(filename)
        git_commit(f"inbox: claude processed {filename}")

if __name__ == '__main__':
    log("=== File Watcher + Claude Started ===")
    handler = InboxHandler()
    observer = PollingObserver(timeout=2)
    observer.schedule(handler, str(INBOX), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("=== Watcher Stopped ===")
        observer.stop()
    observer.join()
