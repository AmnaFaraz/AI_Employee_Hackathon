# Skill: CEO Briefing

## Purpose
Generate a weekly summary report for the CEO saved to Plans/CEO_BRIEFING_<date>.md.

## Workflow
1. Count files in each folder: Inbox, Needs_Action, Pending_Approval, Done
2. Check active watcher status from PID files
3. Summarize recent activity from Logs/
4. Write report to Plans/CEO_BRIEFING_<YYYY-MM-DD>.md
5. Log completion in Logs/ceo_briefing.log

## Report Sections
- Emails Processed (count)
- Pending Approvals (count + list)
- System Health (watcher status)
- Recent Activity (last 10 log entries)

## Rules
- Always include timestamp in filename
- Never overwrite an existing briefing — create new file with today's date
