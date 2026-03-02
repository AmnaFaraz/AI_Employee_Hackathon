#!/bin/bash
VAULT="/mnt/c/Users/dell/Documents/AI_Employee_Vault"
cd "$VAULT"
source venv/bin/activate

echo "[$(date)] Starting File Watcher..." >> Logs/startup.log
python file_watcher.py >> Logs/watcher.log 2>&1 &
echo $! > Logs/file_watcher.pid

echo "[$(date)] Starting Gmail Watcher..." >> Logs/startup.log
python watchers/gmail_watcher.py >> Logs/gmail_watcher.log 2>&1 &
echo $! > Logs/gmail_watcher.pid

echo "[$(date)] Starting Approval Workflow..." >> Logs/startup.log
python approval_workflow.py >> Logs/approval.log 2>&1 &
echo $! > Logs/approval.pid

echo "[$(date)] All systems running." >> Logs/startup.log
