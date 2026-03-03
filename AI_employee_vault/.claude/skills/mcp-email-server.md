# Skill: MCP Email Server

## Purpose
Send emails via Gmail SMTP through the MCP server at mcp_servers/email_server.py.

## When to Use
Only send emails when item is in Approved/ folder and human has reviewed it.

## Workflow
1. Read the approved item from Approved/
2. Extract recipient, subject, and body
3. Call MCP email server to send
4. Log result in Logs/mcp_email.log
5. Move item to Done/

## Rules
- Never send email without human approval first
- Always log every send attempt (success or failure)
- If send fails, log error and move item back to Needs_Action/
