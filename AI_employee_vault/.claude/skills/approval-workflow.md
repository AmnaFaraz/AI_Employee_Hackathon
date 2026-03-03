# Skill: Approval Workflow

## Purpose
Route sensitive items to Pending_Approval/ for human review before any action is taken.

## Sensitive Keywords
payment, invoice, transfer, urgent, contract, legal, bank

## Workflow
1. Scan incoming file or email for sensitive keywords
2. If keyword found → move to Pending_Approval/
3. Log decision in Logs/approval.log
4. Wait for human to move item to Approved/ or Rejected/
5. Never act on items sitting in Pending_Approval/

## Rules
- Never auto-approve sensitive items
- Always log the keyword that triggered routing
- Create PLAN_<filename>.md documenting the reason for escalation
