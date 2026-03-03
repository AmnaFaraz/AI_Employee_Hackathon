import json
import sys
import time
import xmlrpc.client
from pathlib import Path

VAULT = Path('/mnt/c/Users/dell/Documents/AI_employee_vault')
LOG_FILE = VAULT / 'Logs' / 'odoo_mcp.log'

ODOO_URL = "http://localhost:8069"
ODOO_DB = "ai_employee"
ODOO_USER = "admin"
ODOO_PASSWORD = "admin"

def log(msg):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    entry = f"[{timestamp}] {msg}\n"
    with open(LOG_FILE, 'a') as f:
        f.write(entry)
    print(entry.strip(), file=sys.stderr)

def get_uid():
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    return common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})

def odoo_call(model, method, args, kwargs={}):
    uid = get_uid()
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, model, method, args, kwargs)

def create_invoice(partner_name, amount, description):
    partner_ids = odoo_call('res.partner', 'search', [[['name', '=', partner_name]]])
    if not partner_ids:
        partner_id = odoo_call('res.partner', 'create', [{'name': partner_name}])
    else:
        partner_id = partner_ids[0]
    invoice_id = odoo_call('account.move', 'create', [{
        'move_type': 'out_invoice',
        'partner_id': partner_id,
        'invoice_line_ids': [(0, 0, {
            'name': description,
            'quantity': 1,
            'price_unit': amount,
        })]
    }])
    log(f"INVOICE CREATED: id={invoice_id} partner={partner_name} amount={amount}")
    return {"status": "created", "invoice_id": invoice_id}

def get_accounting_summary():
    invoices = odoo_call('account.move', 'search_read',
        [[['move_type', '=', 'out_invoice']]],
        {'fields': ['name', 'partner_id', 'amount_total', 'payment_state'], 'limit': 10}
    )
    log(f"ACCOUNTING SUMMARY: {len(invoices)} invoices retrieved")
    return {"invoices": invoices}

def handle_request(request):
    method = request.get('method')
    params = request.get('params', {})
    if method == 'create_invoice':
        return create_invoice(params['partner'], params['amount'], params['description'])
    elif method == 'get_summary':
        return get_accounting_summary()
    return {"error": "unknown method"}

if __name__ == '__main__':
    log("=== Odoo MCP Server Started ===")
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            result = handle_request(request)
            print(json.dumps(result))
            sys.stdout.flush()
        except Exception as e:
            log(f"ERROR: {e}")
            print(json.dumps({"error": str(e)}))
            sys.stdout.flush()
