# Upwork agent

```
https://github.com/amrkhedr96/upwork-mcp
```

One local MCP server plus one skill. Cursor, Claude, and Codex all talk to the same server. Each person uses their own Upwork API key. The agent searches jobs, analyzes them, drafts a proposal, and submits only after that person says to send it.

## Install

Requires Python 3.11+ and `uv`.

```powershell
cd upwork-mcp
uv run python -m unittest tests.test_workbook tests.test_upwork_client
uv run python install.py
```

`install.py` copies the skill into the local skill folders for Cursor, Codex, and Claude.

## Connect

Replace `C:\path\to\upwork-mcp` with the folder you cloned.

Cursor, `mcp.json`:

```json
"upwork": {
  "command": "uv",
  "args": ["--directory", "C:\\path\\to\\upwork-mcp", "run", "server.py"]
}
```

Codex, `config.toml`:

```toml
[mcp_servers.upwork]
command = "uv"
args = ["--directory", "C:\\path\\to\\upwork-mcp", "run", "server.py"]
```

Claude Code, from the repo folder, reads `.mcp.json`. Or:

```powershell
claude mcp add upwork -- uv --directory C:\path\to\upwork-mcp run server.py
```

Restart the client after adding the server.

## First run for each person

1. Apply for an OAuth 2.0 key: https://www.upwork.com/developer/keys/apply
2. Callback URL: `https://www.upwork.com/ab/messages/rooms/`
3. Ask the agent to save the client id and secret. It stores them under the home `.upwork-mcp` folder and does not print the secret.
4. Open the auth URL, approve, and give the agent the `code` value.
5. Say the kind of jobs to find. The agent searches, analyzes, and shows a proposal preview. It submits when you say to send.

## What the agent does

| Step | Tool |
|---|---|
| Find jobs | `upwork_search_jobs` |
| Read one job | `upwork_job` |
| Analyze and draft | reply, then `upwork_submit_proposal` with `confirm=false` |
| Submit | same tool with `confirm=true` after you say send |
| Chat | `upwork_room_messages`, then `upwork_send_message` |
