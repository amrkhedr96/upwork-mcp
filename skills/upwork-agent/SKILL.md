---
name: upwork-agent
description: >-
  Use when the user mentions Upwork, freelance jobs, proposals, or Connects.
  Works in Cursor, Claude, and Codex through the same local MCP. Search jobs,
  analyze fit, draft a proposal, and submit only after the user explicitly says
  to send it.
---

# Upwork agent

One server. Cursor, Claude, and Codex launch the same process. Each person authorizes their own Upwork account. Never reuse another person's key or token.

Server directory: the folder that contains `server.py`.

Secrets stay on that person's machine. Never print them:

```
~/.upwork-mcp/config.json
~/.upwork-mcp/token.json
```

## Loop

1. `upwork_status`.
2. No key: send them to apply, then `upwork_save_credentials`. No token: `upwork_auth_url`, then `upwork_exchange_code` with the `code` value.
3. `upwork_whoami`. Keep the ids it returns.
4. `upwork_search_jobs` with their skill words. Open the best rows with `upwork_job`.
5. Analyze in the reply: rate, duration, client signals, fit, and why this one is worth a Connect.
6. Draft the cover letter in the chat. Call `upwork_submit_proposal` with `confirm=false` and show the preview.
7. Call it again with `confirm=true` only when this same message explicitly says to submit or send.
8. Messages use the same gate on `upwork_send_message`.

Arabic replies stay Arabic. Job titles, ids, and money go in a table.

## Key scopes

- Common Entities - Read-Only Access
- Read marketplace Job Postings
- Submit Proposal
- Client Proposals - Read And Write Access
- Messaging - Read and Write Access
- Offer - Read-Only Access

Callback URL on the key must match `redirect_uri`. Default:

```
https://www.upwork.com/ab/messages/rooms/
```

Apply:

```
https://www.upwork.com/developer/keys/apply
```

## Tools

| Tool | Effect |
|---|---|
| upwork_search_jobs / upwork_job | Find and read jobs |
| upwork_whoami | Ids required before a proposal |
| upwork_list_proposals / upwork_proposal | Read proposals |
| upwork_list_rooms / upwork_room_messages | Read chat |
| upwork_list_contracts | Read contracts |
| upwork_submit_proposal | Spends Connects only when confirm=true |
| upwork_send_message | Sends only when confirm=true |
| upwork_export_excel | Optional workbook of the account |
