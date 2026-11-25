# Upwork MCP

Updated: 2026-11-25 by cursor

## Where we stopped (update at the end of every session)
- Date / agent: 2026-11-25 cursor
- Goal of last session: Package the server and skill for Cursor, Claude, and Codex
- Done (with evidence): Public repo `https://github.com/amrkhedr96/upwork-mcp` branch `main`, commit `6f5fac2`. No secrets in the tree.
- In progress / half done: Each person still needs their own OAuth key. This account has none.
- Next step: Apply for the key, then `upwork_save_credentials` and `upwork_auth_url`
- Blockers / risks: Live search and submit stay blocked until that key exists. Submit still requires an explicit send.

## What it is
Installable Upwork agent for Cursor, Claude, and Codex. One stdio server and one skill. Each person authorizes their own account. The agent searches, analyzes, drafts, and submits only after that person says to send.

## Where
- Folder: `C:\Users\USER\Projects\upwork-mcp`
- Data / secrets (path only, never contents): `C:\Users\USER\.upwork-mcp\config.json` and `C:\Users\USER\.upwork-mcp\token.json`
- Repo / branch / deploy target: `https://github.com/amrkhedr96/upwork-mcp` branch `main`

## Run
```
uv run python -m unittest tests.test_upwork_client
uv run server.py
```

## Structure
| Path | Purpose |
|---|---|
| server.py | MCP tools |
| upwork_client.py | OAuth and GraphQL |
| workbook.py | Excel export |
| api_catalog.json | 156 documented operations |
| tests/test_upwork_client.py | Auth checks |
| tests/test_workbook.py | Workbook checks |

## Decisions and gotchas
- 2026-11-24: Account API key count was 0. An npm package had been opened in an editor earlier and was not connected.
- Callback on the Upwork key must equal redirect_uri. Default is the messages rooms URL from the official OAuth example.
- confirm=true is the only send switch.

## Log (newest first, keep 5)
- 2026-11-25 cursor: packaged the skill for Cursor, Claude, and Codex. Server was already wired in Cursor and Codex.
- 2026-11-25 cursor: added the full workbook export. 156 operations, live sheets waiting on OAuth.
- 2026-11-24 cursor: created the server, skill, and Cursor MCP entry. Live auth still blocked on an API key.
