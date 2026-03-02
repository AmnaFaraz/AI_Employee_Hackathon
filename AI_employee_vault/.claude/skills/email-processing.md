# Email Processing Skill

## Purpose
Process Gmail emails into vault workflow.

## Flow
1. Gmail API fetches unread emails
2. Save as EMAIL_<id>.md in Needs_Action/
3. Claude Code analyzes content
4. Create PLAN_<id>.md in Plans/
5. Sensitive items → Pending_Approval/
6. Completed items → Done/
7. Update Dashboard.md after each

## File Naming
EMAIL_<timestamp>_<subject-slug>.md

## Required Frontmatter
---
type: email
from: sender@example.com
subject: Subject here
received: 2026-01-01T00:00:00Z
priority: high/normal/low
status: pending
---
