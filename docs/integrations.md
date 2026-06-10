<!-- Copyright (c) 2026, AgriTheory and contributors
For license information, please see license.txt-->

# Desk notifications and chat integrations

<div class="byline">
  Tyler Matteson 2026-04-06
</div>


These features are not part of the public calendar; they extend **Notification** and desk behavior across the site.

## Notification DocType override

`hooks.py` sets **`override_doctype_class`** so **Notification** uses **`CommunicationsNotification`** (`communications.communications.overrides.notification`).

### Extra channels

Beyond standard Frappe channels, the override supports:

- **Slack DM** — uses **Slack Webhook URL** (the linked doc’s webhook value is treated as a **Bot User OAuth Token** for `users_lookupByEmail` and chat post APIs).
- **Teams DM** — uses **Teams Webhook URL**: **Bot App ID**, **Bot App Secret**, **Tenant ID** (and optional fields). The implementation (`TeamsWebhookURL.get_messaging_client()` in `teams_webhook_url.py`) builds a **Bot Framework** client that also uses **Microsoft Graph** (same Entra app, `User.Read.All`) to resolve the recipient to an **Azure AD object id**, then creates a 1:1 chat and posts over the Teams connector. See [Teams setup](./teams_setup.md).

Configure the credential DocTypes, then create **Notification** records with **Channel** = **Slack DM** or **Teams DM** and link the corresponding **Webhook URL** record.

### Teams Webhook URL (Teams DM)

Bot Framework fields plus service URL, etc. Details and Azure permissions are in [teams_setup.md](./teams_setup.md).

## Assignment notifications

On app import, **`communications/__init__.py`** replaces **`frappe.desk.form.assign_to.notify_assignment`** with **`custom_notify_assignment`**.

If an **enabled** **Notification** exists with **Document Type** = **ToDo**, assignment notifications are sent via that **Notification** (queued). Otherwise the code falls back to Frappe-style notification log / email behavior (see `communications.communications.overrides.assign_to`).

### Sliding Window Notification Batching

Assignment notifications can be batched into periodic digest emails instead of sent individually. See [Sliding Window Notification Batching](./sliding_window_notification_batching.md) for configuration and architecture details.

## Phone helpers

**`communications.communications.communications`** exposes **`start_phone_call`** (whitelisted stub). **`validate_phone_number`** and **`validate_data_fields`** implement a North-American-style phone pattern and optional **Data** field checks; they are available for reuse. Core **`frappe.utils.validate_phone_number`** is **not** patched by default (see commented line in `communications/__init__.py`).

## Related

- [Sliding Window Notification Batching](./sliding_window_notification_batching.md)
- [Public Calendar Features](./calendar.md)
- [Video conferencing](./video-conferencing.md)
