
import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

VAULT = Path('/mnt/c/Users/dell/Documents/AI_Employee_Vault')
DROP = VAULT / 'Drop'
DROP.mkdir(exist_ok=True)

class Handler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        print(f"File detected: {Path(event.src_path).name}")
        time.sleep(2)
        # Note: Ensure the 'claude' CLI is installed in your venv or path
        subprocess.run(['claude', '--cwd', str(VAULT), 'Process /Drop file per CLAUDE.md. Update Dashboard. Move to /Done.'])

if __name__ == '__main__':
    print(f"Watching: {DROP}")
    observer = Observer()
    observer.schedule(Handler(), str(DROP), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

