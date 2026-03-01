# Watcher Management Skill

## Purpose
Start, stop, and monitor file_watcher.py and gmail_watcher.py.

## Start File Watcher
```bash
cd /mnt/c/Users/dell/Documents/AI_Employee_Vault
source venv/bin/activate
python file_watcher.py &
echo $! > Logs/file_watcher.pid
```

## Start Gmail Watcher (Silver)
```bash
python watchers/gmail_watcher.py &
echo $! > Logs/gmail_watcher.pid
```

## Check Status
```bash
ps aux | grep watcher
cat Logs/watcher.log
```

## Stop All Watchers
```bash
pkill -f file_watcher.py
pkill -f gmail_watcher.py
```
