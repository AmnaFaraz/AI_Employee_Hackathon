# Vault Management Skill

## Purpose
Manage files across Inbox, Needs_Action, Done, Logs per Hackathon 0 spec.

## Folder Rules
- New files land in: Inbox/
- Files needing action: Needs_Action/
- Completed files: Done/
- All operations logged: Logs/vault.log

## File Move Commands
```bash
mv Inbox/<file> Needs_Action/
mv Needs_Action/<file> Done/
echo "[$(date)] <action>" >> Logs/vault.log
```

## Auto-Commit After Every Move
```bash
git add -A && git commit -m "vault: <description>" && git push
```
