# AI Employee Dashboard
*Last Updated: 2026-03-03 05:05:45*

## Status: 🟢 RUNNING

## Folder Counts
| Folder | Files |
|--------|-------|
| Inbox | 0 |
| Needs_Action | 31 |
| Pending_Approval | 7 |
| Approved | 0 |
| Done | 0 |

## Active Watchers
- file_watcher.py → monitoring Inbox/
- gmail_watcher.py → monitoring Gmail
- approval_workflow.py → routing items

## Architecture
PERCEPTION (Watchers) → REASONING (Claude Code) → ACTION (MCP) → STORAGE (Vault)
