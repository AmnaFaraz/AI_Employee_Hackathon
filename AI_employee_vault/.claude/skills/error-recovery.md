# Skill: Error Recovery

## Purpose
Monitor running processes and automatically restart any that have crashed.

## Monitored Processes
- file_watcher.py
- watchers/gmail_watcher.py
- approval_workflow.py
- update_dashboard.py
- ralph_wiggum.py

## Workflow
1. Check each process PID file in Logs/
2. If process not running → restart it
3. Log restart event in Logs/error_recovery.log
4. If process fails 3 times in 10 minutes → alert and stop retrying

## Rules
- Always log every restart attempt with timestamp
- Never restart more than 3 times without human intervention
- Update Dashboard.md after any restart event
