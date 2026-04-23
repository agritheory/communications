<!-- Copyright (c) 2026, AgriTheory and contributors
For license information, please see license.txt-->

# Teams DM integration (Bot Framework)

How to send **Microsoft Teams** direct messages from ERPNext when a **Notification** fires, using the **Bot Framework** connector and the **Teams Webhook URL** doctype.

## How it works

1. **Notification** (channel **Teams DM**) loads the linked **Teams Webhook URL** and builds a `TeamsMessagingClient` (see [Implementation](#implementation) below).
2. The app resolves each recipient to an **Azure AD object ID (GUID)**. It uses the **Microsoft Graph** `GET /users/...` flow with the **same** Entra app as the bot (`client_credentials` to `https://graph.microsoft.com/.default`), or a **Social ID** row (provider `teams`, user id = GUID) if you set one.
3. It **creates a 1:1 conversation** and sends the message via the **Bot Framework REST API** (`https://smba.trafficmanager.net/teams/...`).

Proactive DMs need the **bot app installed for the user in personal scope** in Teams. If the API returns an error that the bot is not installed, the user must add your Teams app (or an admin must deploy it) once.

**Message body:** notification templates are usually HTML. The client converts HTML to **markdown** and sends with `textFormat: markdown` (Teams does not accept `textFormat: html` for this path).

## Azure: bot + Entra app

1. In **Azure Portal**, create or open an **Azure Bot** and connect the **Microsoft Teams** channel.
2. Note **Microsoft App ID** and create a **client secret** — these are **Bot App ID** and **Bot App Secret** in ERPNext.
3. In **Microsoft Entra ID** → your app registration (same as the bot’s app) → **API permissions** → **Application permissions** for **Microsoft Graph**:
   - **`User.Read.All`** (or another permission that allows reading user directory data to resolve email/UPN to an object id), with **admin consent**.

The bot uses that permission only to look up users; delivery is still **Bot Framework** + Teams connector.

## ERPNext: Teams Webhook URL

Create **Teams Webhook URL** (Communications) with at least:

| Field | Notes |
|--------|--------|
| **Name** | Label in Notification (e.g. "Teams DM bot"). |
| **Bot App ID** | Azure Bot Microsoft App ID. |
| **Bot App Secret** | The secret for that app. |
| **Tenant ID** | Entra tenant (directory) **GUID**. |
| **Service URL** | Default `https://smba.trafficmanager.net/teams/` unless Microsoft specifies otherwise. |
| **Tenant Domain** | Optional; description on the doctype; not required for the current resolution path. |
| **Show link to document** | Appends a link in the message when enabled. |

**Webhook URL** in the doctype is for other flows (e.g. channel webhooks), not the DM path described here.

## Notification

1. **Notification** → **Channel** = **Teams DM**.
2. **Teams Channel** = your **Teams Webhook URL** name.
3. **Recipients** = emails that match **Entra** (mail/UPN) for Graph lookup, or map users via [Social ID](#user-mapping-optional).
4. Save and test on a low-risk doctype, or use **Error Log** if something fails. Error titles are short; the **Error** field holds the full message (e.g. 403 *bot not installed in user's personal scope*).

## User mapping (optional)

- **Default:** match notification recipient to an Entra user by **email / UPN** (Graph).
- **Social ID (provider `teams`, User ID = Azure AD object ID):** skip Graph for that user when the value looks like a GUID. Useful for fixed mappings or if you prefer not to rely on directory lookup.

## Troubleshooting (short)

| Symptom | What to check |
|--------|----------------|
| Graph / "Entra user lookup" errors | `User.Read.All` (app) + admin consent; recipient exists in the tenant. |
| **403** *Bot is not installed in user's personal scope* | User opens **Apps** in Teams, adds your bot, starts a 1:1 chat; or admin deploys the app. |
| **400** message format | Should not happen with current app (HTML is converted to markdown). |
| Token errors | Bot App ID, secret, tenant; bot not disabled; multi-tenant may use the second token authority (handled in code). |

## Implementation

Controller and client live in one module:

- **`communications.communications.doctype.teams_webhook_url.teams_webhook_url`**
  - **`TeamsWebhookURL`** (Document) — `validate`, `get_messaging_client()`.
  - **`TeamsMessagingClient`** — tokens, Graph user resolution, `create_conversation`, `send_message_to_conversation`, `send_dm_to_user`.
  - Exceptions: **`TeamsMessagingError`**, **`ConversationCreationError`**, **`MessageSendError`**, **`TokenAcquisitionError`**.

**Notification** override imports **`TeamsMessagingError`** from that module for error logging.

### Example (script / bench)

```python
import frappe
from communications.communications.doctype.teams_webhook_url.teams_webhook_url import TeamsMessagingClient

def send_example():
	wh = frappe.get_doc("Teams Webhook URL", "My Bot Name")
	client = wh.get_messaging_client()
	client.send_dm_to_user("user@contoso.com", message="<p>Hello</p>", content_type="html")
```

Or construct the client yourself if you are not using a stored doc:

```python
from communications.communications.doctype.teams_webhook_url.teams_webhook_url import TeamsMessagingClient

client = TeamsMessagingClient(
	bot_app_id="…",
	bot_app_secret="…",
	tenant_id="…",
	tenant_domain=None,
	service_url="https://smba.trafficmanager.net/teams/",
)
client.send_dm_to_user("user@contoso.com", message="<p>Hello</p>")
```

## Related

- [Desk notifications and chat integrations](./integrations.md) (Slack DM, override overview).
