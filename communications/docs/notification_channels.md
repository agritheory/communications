<!-- Copyright (c) 2026, AgriTheory and contributors
For license information, please see license.txt-->

# Notification Channels

<div class="byline">
  Tyler Matteson 2026-06-24
</div>


These features extend **Notification** and desk behavior across the site. They are separate from the [Public Calendar](./public_calendar.md) booking flow.

## Notification DocType override

`hooks.py` sets **`override_doctype_class`** so **Notification** uses **`CommunicationsNotification`** (`communications.communications.overrides.notification`).

## Extra channels

Beyond standard Frappe channels (Email, Slack, System Notification, SMS, Teams), the override supports:

- **Slack DM** — uses Frappe core **Slack Webhook URL**. The linked record’s **Webhook URL** field holds a **Bot User OAuth Token** used for `users_lookupByEmail` and `chat.postMessage`. See [Slack DM Setup](./slack_setup.md).
- **Teams DM** — uses **Teams Webhook URL** (**Bot App ID**, **Bot App Secret**, **Tenant ID**, and related fields). The implementation builds a **Bot Framework** client that also uses **Microsoft Graph** to resolve the recipient to an Azure AD object id, then creates a 1:1 chat and posts over the Teams connector. See [Teams DM Setup](./teams_setup.md).

Configure the credential DocTypes, then create **Notification** records with **Channel** = **Slack DM** or **Teams DM** and link the corresponding webhook record.

DM notifications are enqueued as background jobs after commit when the referenced document is submitted; otherwise they send synchronously.

## Email Override

On app import, **`email_override_patches.py`** patches specific Frappe email emitters so configured **Notification** records can replace selected stock emails (desk **Notification Log** types, document follow, workflow, event digest).

Set **Email Override** on each **Notification** row (e.g. **Mention**, **Assignment**, **Document Follow**). Password reset and other site emails use different call sites and are not intercepted.

Full scope, configuration, and examples: **[Email Override](./email_override.md)**.

## Assignment notifications

Assignment email uses the same path as other Notification Log types: Frappe creates a **`type: Assignment`** log, then **`send_notification_email`** runs. Configure a **Notification** with **Email Override** = **Assignment** to route delivery (Email, Slack DM, Teams DM, etc.).

Assignment notifications can also be batched into periodic digest emails instead of sent individually. See [Assignment Notification Batching](./notification_batching.md).

## Related

- [Slack DM Setup](./slack_setup.md)
- [Teams DM Setup](./teams_setup.md)
- [Email Override](./email_override.md)
- [Assignment Notification Batching](./notification_batching.md)
- [Public Calendar](./public_calendar.md)
- [Video Conferencing](./video_conferencing.md)
- [Phone Helpers](./phone_helpers.md)
