#!/bin/bash
VAULT="/mnt/c/Users/dell/Documents/AI_Employee_Vault"
cd "$VAULT"
source venv/bin/activate
LOG="$VAULT/Logs/startup.log"

echo "[$(date)] === AI EMPLOYEE STARTUP ===" >> $LOG

echo "[$(date)] Starting File Watcher..." >> $LOG
python file_watcher.py >> Logs/watcher.log 2>&1 &
echo $! > Logs/file_watcher.pid

echo "[$(date)] Starting Gmail Watcher..." >> $LOG
python watchers/gmail_watcher.py >> Logs/gmail_watcher.log 2>&1 &
echo $! > Logs/gmail_watcher.pid

echo "[$(date)] Starting Approval Workflow..." >> $LOG
python approval_workflow.py >> Logs/approval.log 2>&1 &
echo $! > Logs/approval.pid

echo "[$(date)] Starting Dashboard Updater..." >> $LOG
python update_dashboard.py >> Logs/dashboard.log 2>&1 &
echo $! > Logs/dashboard.pid

echo "[$(date)] Starting Error Recovery..." >> $LOG
python error_recovery.py >> Logs/error_recovery.log 2>&1 &
echo $! > Logs/recovery.pid

echo "[$(date)] Starting Ralph Wiggum Loop..." >> $LOG
python ralph_wiggum.py >> Logs/ralph.log 2>&1 &
echo $! > Logs/ralph.pid

echo "[$(date)] ALL SYSTEMS RUNNING" >> $LOG
echo "All AI Employee systems started."
ps aux | grep python | grep -v grep
