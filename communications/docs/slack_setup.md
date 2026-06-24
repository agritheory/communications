<!-- Copyright (c) 2026, AgriTheory and contributors
For license information, please see license.txt-->

# Slack DM Setup

<div class="byline">
  Tyler Matteson 2026-06-24
</div>


How to send **Slack** direct messages from ERPNext when a **Notification** fires, using a Slack app **Bot User OAuth Token** and Frappe core **Slack Webhook URL**.

## How it works

1. **Notification** (channel **Slack DM**) loads the linked **Slack Webhook URL** record.
2. **`CommunicationsNotification.get_slack_user_id()`** calls Slack **`users.lookupByEmail`** with the recipient’s email to resolve a Slack user id.
3. **`send_a_slack_dm_msg()`** posts a Block Kit message via **`chat.postMessage`** to that user id (a DM channel).

Notification templates are rendered as Jinja; the client sends structured blocks with the subject and message body. When **Show link to document** is enabled on the webhook record, a link to the referenced form is appended.

## Slack app configuration

1. Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps) (or use an existing workspace app).
2. Under **OAuth & Permissions**, add **Bot Token Scopes** at minimum:
   - **`users:read.email`** — resolve ERPNext user email to Slack user id
   - **`chat:write`** — post messages
   - **`im:write`** — open or use DM channels with users
3. **Install the app to your workspace** and copy the **Bot User OAuth Token** (starts with `xoxb-`).
4. Ensure workspace members who should receive DMs have an email on their Slack profile that matches their ERPNext **User** email.

## ERPNext: Slack Webhook URL

**Slack Webhook URL** is a Frappe core DocType (Integrations module). Create a record with:

| Field | Notes |
|--------|--------|
| **Name** | Label used when linking from **Notification** (e.g. `Slack DM bot`). |
| **Webhook URL** | Paste the **Bot User OAuth Token** (`xoxb-…`), not an incoming webhook URL. |
| **Show link to document** | Optional; appends a form link in the DM when enabled. |

Despite the field name, Communications treats **Webhook URL** as the bot token for the DM path.

## Notification

1. Open **Notification** → set **Channel** = **Slack DM**.
2. **Slack Webhook URL** = the record created above.
3. Configure **Subject**, **Message** (Jinja), and **Recipients** as for any Notification.
4. For routed desk emails, set **Email Override** instead of doc-event triggers; see [Email Override](./email_override.md).

Save and test on a low-risk document or Notification Log type. Failures are logged on the **Notification** error log.

## Troubleshooting

| Symptom | What to check |
|--------|----------------|
| `users_not_found` / lookup errors | Recipient email must match a Slack workspace member; **`users:read.email`** scope required. |
| `not_in_channel` / DM errors | Bot needs **`im:write`**; user may need to have interacted with the app once. |
| `invalid_auth` | Token revoked or wrong token type; reinstall app and update **Slack Webhook URL**. |
| Empty message | Check Jinja in **Message**; for Email Override routes use `sendmail_subject` / `sendmail_message` variables. |

## Related

- [Notification Channels](./notification_channels.md)
- [Email Override](./email_override.md)
- [Teams DM Setup](./teams_setup.md)
