
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
