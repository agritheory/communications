<!-- Copyright (c) 2026, AgriTheory and contributors
For license information, please see license.txt-->

# Desk notifications and chat integrations

These features are not part of the public calendar; they extend **Notification** and desk behavior across the site.

## Notification DocType override

`hooks.py` sets **`override_doctype_class`** so **Notification** uses **`CommunicationsNotification`** (`communications.communications.overrides.notification`).

### Extra channels

Beyond standard Frappe channels, the override supports:

- **Slack DM** — uses **Slack Webhook URL** (the linked doc’s webhook value is treated as a **Bot User OAuth Token** for `users_lookupByEmail` and chat post APIs).
- **Teams DM** — uses **Teams Webhook URL** (Microsoft Graph client credentials) to resolve the recipient by email and send a Teams message.

Configure the webhook/credential DocTypes, then create **Notification** records with **Channel** = **Slack DM** or **Teams DM** and link the corresponding URL record.

### Teams Webhook URL

Stores **tenant_id**, **client_id**, **client_secret** (password), **tenant_domain** (optional, for guest/external user lookup), and related options. **`client()`** obtains a Graph API bearer token and returns a `requests` session scoped to `https://graph.microsoft.com/v1.0`.

## Assignment notifications

On app import, **`communications/__init__.py`** replaces **`frappe.desk.form.assign_to.notify_assignment`** with **`custom_notify_assignment`**.

If an **enabled** **Notification** exists with **Document Type** = **ToDo**, assignment notifications are sent via that **Notification** (queued). Otherwise the code falls back to Frappe-style notification log / email behavior (see `communications.communications.overrides.assign_to`).

## Phone helpers

**`communications.communications.communications`** exposes **`start_phone_call`** (whitelisted stub). **`validate_phone_number`** and **`validate_data_fields`** implement a North-American-style phone pattern and optional **Data** field checks; they are available for reuse. Core **`frappe.utils.validate_phone_number`** is **not** patched by default (see commented line in `communications/__init__.py`).

## Related

- [Public Calendar Features](./calendar.md)
- [Video conferencing](./video-conferencing.md)
