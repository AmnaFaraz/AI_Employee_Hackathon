# AI Employee — Autonomous Digital FTE

An autonomous, local-first AI system built on Claude Code and Obsidian that monitors, reasons, and acts on emails and files with human-in-the-loop approval.

---

## Architecture

```
PERCEPTION          REASONING           ACTION              STORAGE
─────────────────────────────────────────────────────────────────────
Gmail Watcher   →   Claude Code     →   MCP Email Server →  Obsidian Vault
File Watcher    →   Agent Skills    →   Git Commits      →  GitHub Repo
                →   Approval Logic  →   Dashboard Update →  Logs
```

---

## Project Structure

```
AI_Employee_Vault/
├── .claude/
│   └── skills/
│       ├── vault-management.md
│       ├── email-processing.md
│       ├── watcher-management.md
│       ├── approval-workflow.md
│       ├── mcp-email-server.md
│       ├── ceo-briefing.md
│       └── error-recovery.md
├── Inbox/                  ← New files arrive here
├── Needs_Action/           ← Claude processes these
├── Plans/                  ← Claude's reasoning + action plans
├── Pending_Approval/       ← Awaiting human review
├── Approved/               ← Human approved, ready to execute
├── Rejected/               ← Human rejected
├── Done/                   ← Completed tasks
├── Logs/                   ← All system activity
│   ├── watcher.log
│   ├── gmail_watcher.log
│   ├── approval.log
│   ├── mcp_email.log
│   ├── ceo_briefing.log
│   ├── error_recovery.log
│   └── ralph.log
├── watchers/
│   └── gmail_watcher.py
├── mcp_servers/
│   └── email_server.py
├── file_watcher.py
├── approval_workflow.py
├── update_dashboard.py
├── ceo_briefing.py
├── error_recovery.py
├── ralph_wiggum.py
├── start_all_watchers.sh
├── CLAUDE.md
├── CONSTITUTION.md
├── Company_Handbook.md
└── Dashboard.md
```

---

## System Components

### Watchers (Perception Layer)
| File | Purpose |
|------|---------|
| `file_watcher.py` | Monitors `Inbox/` using PollingObserver (WSL2 compatible) |
| `watchers/gmail_watcher.py` | Polls Gmail API every 2 minutes for unread emails |

### Claude Code (Reasoning Layer)
| File | Purpose |
|------|---------|
| `CLAUDE.md` | Defines Claude's role, skills, and rules |
| `.claude/skills/*.md` | Agent skill definitions Claude reads before acting |

### Action Layer
| File | Purpose |
|------|---------|
| `approval_workflow.py` | Routes sensitive items to `Pending_Approval/` |
| `mcp_servers/email_server.py` | MCP server for sending emails via Gmail SMTP |
| `ralph_wiggum.py` | Autonomous loop — auto-resolves safe items |

### Storage + Reporting
| File | Purpose |
|------|---------|
| `update_dashboard.py` | Updates `Dashboard.md` every 60 seconds |
| `ceo_briefing.py` | Generates weekly CEO report in `Plans/` |
| `error_recovery.py` | Monitors and restarts crashed processes |

---

## Prerequisites

- Windows 10 Pro + WSL2 (Ubuntu 22.04)
- Python 3.13
- Node.js 20.x
- Claude Code (Anthropic Pro subscription)
- Obsidian
- Git

---

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/AmnaFaraz/AI_Employee_Hackathon.git
cd AI_Employee_Hackathon
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install watchdog google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### 4. Install Claude Code

```bash
npm install -g @anthropic-ai/claude-code
claude --version
```

### 5. Setup Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create project: `AI-Employee-Silver`
3. Enable Gmail API
4. Create OAuth 2.0 credentials (Desktop App)
5. Download `credentials.json`
6. Place in `watchers/credentials.json`

### 6. Authenticate Gmail

```bash
python watchers/gmail_watcher.py
```

Browser opens → Sign in → Allow → `token.json` created automatically.

---

## Configuration

### CLAUDE.md
Defines Claude Code's operating instructions — role, workflow, folder meanings, and rules.

### CONSTITUTION.md
Core rules Claude must never violate:
- Never act without logging
- Always create a plan before acting
- Sensitive items always go to `Pending_Approval/`
- Human approval required before sending emails
- Never delete files — only move them

### .gitignore
```
venv/
watchers/token.json
watchers/credentials.json
*.pyc
__pycache__/
```

---

## Running the System

### Start All Components

```bash
cd /mnt/c/Users/dell/Documents/AI_Employee_Vault
./start_all_watchers.sh
```

This starts:
1. `file_watcher.py` — File monitoring
2. `gmail_watcher.py` — Gmail monitoring
3. `approval_workflow.py` — Routing logic
4. `update_dashboard.py` — Dashboard updates
5. `error_recovery.py` — Process monitoring
6. `ralph_wiggum.py` — Autonomous loop

### Start Individual Components

```bash
source venv/bin/activate

# File watcher only
python file_watcher.py

# Gmail watcher only
python watchers/gmail_watcher.py

# Generate CEO briefing
python ceo_briefing.py
```

### Check Status

```bash
ps aux | grep python | grep -v grep
cat Logs/watcher.log
cat Logs/gmail_watcher.log
```

### Stop All

```bash
pkill -f file_watcher.py
pkill -f gmail_watcher.py
pkill -f approval_workflow.py
pkill -f update_dashboard.py
pkill -f error_recovery.py
pkill -f ralph_wiggum.py
```

---

## Workflow

### File Processing Flow

```
1. File dropped in Inbox/
2. file_watcher.py detects it
3. Claude Code reads file + CLAUDE.md + skills
4. Claude decides: Needs_Action/ or Done/
5. Claude creates PLAN_<file>.md in Plans/
6. Dashboard.md updated
7. Git commit + push
```

### Email Processing Flow

```
1. Unread email arrives in Gmail
2. gmail_watcher.py fetches it every 120 seconds
3. Email saved as EMAIL_<timestamp>_<subject>.md in Needs_Action/
4. Claude reads email + email-processing.md skill
5. Sensitive keywords → Pending_Approval/
6. Claude creates PLAN_<file>.md in Plans/
7. Dashboard.md updated
8. Git commit + push
```

### Approval Flow

```
1. Item lands in Pending_Approval/
2. Human reviews in Obsidian
3. Human moves to Approved/ or Rejected/
4. approval_workflow.py detects move
5. Approved/ → processed → Done/
6. Rejected/ → logged → no action
```

---

## Sensitive Keyword Triggers

Items containing these words auto-route to `Pending_Approval/`:

```
payment, invoice, transfer, urgent, contract, legal, bank
```

---

## Dashboard

`Dashboard.md` auto-updates every 60 seconds showing:
- Folder file counts (Inbox, Needs_Action, Pending, Done)
- Active watcher status
- Last updated timestamp

---

## CEO Weekly Briefing

Run manually or schedule weekly:

```bash
python ceo_briefing.py
```

Output: `Plans/CEO_BRIEFING_<date>.md`

Contains:
- Emails processed count
- Pending approvals
- System health status
- Recent activity log

---

## Windows Auto-Start (Task Scheduler)

Configured to run `start_all_watchers.sh` on system startup via Windows Task Scheduler:

- **Program:** `wsl.exe`
- **Arguments:** `-d Ubuntu-22.04 -e bash /mnt/c/Users/dell/Documents/AI_Employee_Vault/start_all_watchers.sh`
- **Trigger:** At system startup

---

## Agent Skills Reference

| Skill File | What Claude Reads It For |
|------------|--------------------------|
| `vault-management.md` | File routing rules and git commit format |
| `email-processing.md` | Email parsing and priority classification |
| `watcher-management.md` | How to start/stop/check watchers |
| `approval-workflow.md` | Sensitive keyword detection and routing |
| `mcp-email-server.md` | How to send emails via MCP |
| `ceo-briefing.md` | Weekly report generation |
| `error-recovery.md` | Process restart procedures |

---

## Logs Reference

| Log File | Contains |
|----------|----------|
| `Logs/watcher.log` | File detection events |
| `Logs/gmail_watcher.log` | Email fetch events |
| `Logs/approval.log` | Routing decisions |
| `Logs/mcp_email.log` | Emails sent via MCP |
| `Logs/ceo_briefing.log` | Briefing generation events |
| `Logs/error_recovery.log` | Process restart events |
| `Logs/ralph.log` | Autonomous loop decisions |
| `Logs/dashboard.log` | Dashboard update events |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Reasoning | Claude Code (Anthropic) |
| Knowledge Base | Obsidian Vault |
| Email Perception | Gmail API v1 |
| File Perception | Watchdog (PollingObserver) |
| MCP Server | Python SMTP |
| Version Control | Git + GitHub |
| Runtime | Python 3.13 + WSL2 Ubuntu 22.04 |
| OS | Windows 10 Pro |

---

## Author

**Amna Faraz**
GitHub: [@AmnaFaraz](https://github.com/AmnaFaraz)
Email: amnafaraz89@gmail.com

---

## Architecture & Design Decisions

The system is built around four distinct layers that mirror how a human employee operates:

**Perception** handles all incoming signals — emails via Gmail API and files via filesystem polling. PollingObserver is used instead of inotify because WSL2 does not support inotify events on Windows-mounted drives (`/mnt/c/`).

**Reasoning** is handled entirely by Claude Code, which reads `.claude/skills/*.md` before every decision. Skills act as bounded instructions that keep Claude's behavior predictable and auditable. Every decision produces a `Plans/PLAN_*.md` file documenting Claude's reasoning.

**Action** is executed only after human approval for sensitive items. The MCP servers (email, Odoo, social) are called only when an item reaches `Approved/`. This enforces human-in-the-loop as an architectural guarantee rather than a policy.

**Storage** is Obsidian-compatible markdown, meaning every file is human-readable, version-controlled via Git, and visible in Obsidian without any special tooling.

---

## Lessons Learned

**WSL2 filesystem limitation:** The Watchdog library's default inotify observer does not work on `/mnt/c/` paths. Switching to `PollingObserver` with a 2-second timeout resolved all detection failures.

**GitHub push protection:** OAuth tokens must never be committed. The `watchers/token.json` file was added to `.gitignore` after an initial blocked push due to embedded secrets.

**Emoji in filenames:** Email subjects containing emoji characters caused `FileNotFoundError` on the Windows filesystem. A `safe_filename()` function strips non-ASCII characters before creating any file.

**Credential management:** The Google OAuth consent screen requires the test user's email to be explicitly added as an authorised tester before the OAuth flow can complete — this is not documented prominently in Google's quickstart guides.

**Agent Skills design:** Keeping Claude's instructions in `.claude/skills/*.md` files rather than hardcoding prompts means behaviour can be updated without touching any Python code, which makes the system maintainable by non-developers.
