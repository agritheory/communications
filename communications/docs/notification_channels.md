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

When emails are muted (`mute_emails` in site config or `frappe.flags.mute_emails`), Slack DM sends are skipped for doc-event notifications. Nothing is posted and nothing is written to the Error Log. Email Override routes still send. Unmute the site to test Slack DM delivery locally.

## Receiver By Hook

Each row in the **Notification** recipients child table can set **Receiver By Hook** (Autocomplete). Options come from the `notification_recipients` hook registry in each app’s `hooks.py`. The key is a human-readable title (for example **Sales Team**); that exact string is stored on the row and shown in the Autocomplete.

Register a resolver:

```python
notification_recipients = {
	"Sales Team": "my_app.notifications.sales_order_team",
}
```

The resolver is called as `fn(doc, notification, recipient_row, context)` and must return a list of email addresses and/or User names. Results are normalized to email and merged with **Receiver By Document Field**, **Receiver By Role**, and CC/BCC on the same row. Values that are neither a valid email nor an existing User are dropped. The row’s **Condition** still gates whether that row runs (including the hook). If multiple apps register the same title, the last installed app wins.

A resolver that raises is logged on the **Notification** error log and contributes no recipients; the rest of the rows still send. Saving a **Notification** whose row names an unregistered hook fails validation, so renaming a key in `hooks.py` requires updating existing rows.

`CommunicationsNotification.get_list_of_recipients` applies hooks for Email, Slack DM, Teams DM, and System Notification. SMS is unchanged.

Run `bench migrate` after installing to sync the **Receiver By Hook** custom field (`custom/notification_recipient.json`).

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
