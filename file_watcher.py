import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
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

class InboxHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory or event.src_path.endswith('.gitkeep'):
            return
        filename = Path(event.src_path).name
        log(f"NEW FILE DETECTED: {filename}")
        git_commit(f"inbox: new file {filename}")

if __name__ == '__main__':
    log("=== File Watcher Started - Monitoring Inbox/ ===")
    handler = InboxHandler()
    observer = Observer()
    observer.schedule(handler, str(INBOX), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("=== File Watcher Stopped ===")
        observer.stop()
    observer.join()
