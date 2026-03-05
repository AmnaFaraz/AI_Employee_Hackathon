# Skill: Odoo Accounting MCP

## Purpose
Create invoices and retrieve accounting summaries from Odoo Community via JSON-RPC.

## Odoo Setup
- URL: http://localhost:8069
- Database: ai_employee
- Start server: mcp_servers/odoo_server.py

## Available Methods

### create_invoice
Input:
{"method": "create_invoice", "params": {"partner": "Client Name", "amount": 500, "description": "Service rendered"}}

### get_summary
Input:
{"method": "get_summary", "params": {}}

## Logs
Logs/odoo_mcp.log

## Rules
- Only create invoices for Approved/ items
- Always log every Odoo transaction
- Include invoice ID in git commit message
