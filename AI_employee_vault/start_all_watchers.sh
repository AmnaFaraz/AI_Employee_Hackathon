#!/bin/bash
VAULT="/mnt/c/Users/dell/Documents/AI_employee_vault"
cd "$VAULT"
source venv/bin/activate
LOG="$VAULT/Logs/startup.log"

echo "[$(date)] === AI EMPLOYEE STARTUP ===" >> $LOG

python file_watcher.py >> Logs/watcher.log 2>&1 &
echo $! > Logs/file_watcher.pid
echo "[$(date)] File Watcher started" >> $LOG

python watchers/gmail_watcher.py >> Logs/gmail_watcher.log 2>&1 &
echo $! > Logs/gmail_watcher.pid
echo "[$(date)] Gmail Watcher started" >> $LOG

python approval_workflow.py >> Logs/approval.log 2>&1 &
echo $! > Logs/approval.pid
echo "[$(date)] Approval Workflow started" >> $LOG

python update_dashboard.py >> Logs/dashboard.log 2>&1 &
echo $! > Logs/dashboard.pid
echo "[$(date)] Dashboard Updater started" >> $LOG

python error_recovery.py >> Logs/error_recovery.log 2>&1 &
echo $! > Logs/recovery.pid
echo "[$(date)] Error Recovery started" >> $LOG

python ralph_wiggum.py >> Logs/ralph.log 2>&1 &
echo $! > Logs/ralph.pid
echo "[$(date)] Ralph Wiggum started" >> $LOG

python watchers/linkedin_poster.py >> Logs/linkedin.log 2>&1 &
echo $! > Logs/linkedin.pid
echo "[$(date)] LinkedIn Poster started" >> $LOG

python watchers/social_poster.py >> Logs/social.log 2>&1 &
echo $! > Logs/social.pid
echo "[$(date)] Social Poster started" >> $LOG

python watchers/twitter_poster.py >> Logs/twitter.log 2>&1 &
echo $! > Logs/twitter.pid
echo "[$(date)] Twitter Poster started" >> $LOG

echo "[$(date)] ALL SYSTEMS RUNNING" >> $LOG
echo "All AI Employee systems started."
ps aux | grep python | grep -v grep
