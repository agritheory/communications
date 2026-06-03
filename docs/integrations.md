<!-- Copyright (c) 2026, AgriTheory and contributors
For license information, please see license.txt-->

# Desk notifications and chat integrations

<div class="byline">
  Tyler Matteson 2026-06-02
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

## Email Override

On app import, **`communications/communications/communications/email_override_patches.py`** patches specific Frappe email emitters so configured **Notification** records can replace selected stock emails (desk **Notification Log** types, document follow, workflow, event digest).

Set **Email Override** on each **Notification** row (e.g. **Mention**, **Assignment**, **Document Follow**). Password reset and other site emails use different call sites and are not intercepted.

Full scope, configuration, and examples: **[Email Override](./sendmail-routes.md)**.

## Assignment notifications

Assignment email uses the same path as other Notification Log types: Frappe creates a **`type: Assignment`** log, then **`send_notification_email`** runs. Configure a **Notification** with **Email Override** = **Assignment** to route delivery (Email, Slack DM, Teams DM, etc.).

## Phone helpers

**`communications.communications.communications`** exposes **`start_phone_call`** (whitelisted stub). **`validate_phone_number`** and **`validate_data_fields`** implement a North-American-style phone pattern and optional **Data** field checks; they are available for reuse. Core **`frappe.utils.validate_phone_number`** is **not** patched by default (see commented line in `communications/__init__.py`).

## Related

- [Email Override](./sendmail-routes.md)
- [Public Calendar Features](./calendar.md)
- [Video conferencing](./video-conferencing.md)
