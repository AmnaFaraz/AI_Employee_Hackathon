# AI Employee Dashboard
*Last Updated: 2026-03-03 03:20:34*

## Status: 🟢 RUNNING

## Folder Counts
| Folder | Files |
|--------|-------|
| Inbox | 0 |
| Needs_Action | 21 |
| Pending_Approval | 4 |
| Approved | 0 |
| Done | 0 |

## Active Watchers
- file_watcher.py → monitoring Inbox/
- gmail_watcher.py → monitoring Gmail
- approval_workflow.py → routing items

## Architecture
PERCEPTION (Watchers) → REASONING (Claude Code) → ACTION (MCP) → STORAGE (Vault)
