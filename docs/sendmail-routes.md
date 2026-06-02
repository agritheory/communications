<!-- Copyright (c) 2026, AgriTheory and contributors
For license information, please see license.txt-->

# Email Override

<div class="byline">
  Tyler Matteson 2026-06-02
</div>

On app import, **`communications/__init__.py`** applies **targeted patches** to Frappe email emitters so selected outbound emails can be handled by **Notification** records (via **`CommunicationsNotification`**) instead of stock **`frappe.sendmail`**.

Admins configure intercepts with the **Email Override** Select field on **Notification** (custom field in Desk). There is no Python tuple or JSON match configuration.

## Email Override options

| Email Override | Frappe function patched | Trigger |
|----------------|-------------------------|---------|
| **Mention, Assignment, Share, Energy Point, Alert** | `send_notification_email` | Any Notification Log email whose `type` is one of these |
| **Document Follow** | `send_email_alert` | Scheduled document-follow digest |
| **Workflow Action** | `send_workflow_action_email` | Workflow approval email |
| **Event Digest** | `send_event_digest` | Daily calendar reminder email |

The first option is a **single Select value** (one line in the field definition). Notification Log routing matches on `Notification Log.type` at runtime; it is not a separate option per log type.

Leave **Email Override** blank for standard doc-event **Notification** rows (Save, Submit, etc.).

## What `send_notification_email` is

In Frappe core, **`send_notification_email`** lives in `frappe/desk/doctype/notification_log/notification_log.py`. It is the only function that sends email for desk **Notification Log** rows.

Flow:

1. Desk creates a **Notification Log** (via **`enqueue_create_notification`**).
2. If email is enabled for that log’s **`type`**, **`send_notification_email`** runs.
3. Communications intercepts when an enabled **Notification** exists with matching **Email Override** (= log **`type`**).
4. **`CommunicationsNotification.send(doc)`** runs for the referenced business document; stock **`frappe.sendmail`** is skipped.

| `type` | Typical trigger |
|--------|-----------------|
| **Mention** | `@` mention in a **Comment** |
| **Assignment** | Document assignment |
| **Share** | Document shared |
| **Energy Point** | Energy point award (skipped when `email_content` is `None`) |
| **Alert** | Desk/system alerts, reminders |

**Not** intercepted: password reset, welcome mail, **Notification** doc-event emails, newsletters, **Auto Email Report**, contact form, 2FA, backups, etc. See [sendmail-call-sites.md](./sendmail-call-sites.md).

## How routing works

1. **Cache** — `build_email_override_cache()` loads enabled **Notification** rows grouped by **`email_override`** (invalidated on Notification save/trash).
2. **Patch** — Each emitter checks `notifications_for_override(value)`; if any match, **`try_email_override`** lifts **`sendmail`** kwargs into template locals and calls **`Notification.send(doc)`**.
3. **Reference document** — Usually the business document from the log or **`sendmail`** kwargs. **Event Digest** uses the recipient **User** as template context.
4. **Re-entry guard** — **`frappe.local.in_email_override`** lets **`CommunicationsNotification.send_an_email`** call stock **`frappe.sendmail`** without looping.

### Template variables (routed sends)

| Variable | Source |
|----------|--------|
| `doc` | Context document (referenced doc or User for Event Digest) |
| `sendmail_subject` | Original email subject |
| `sendmail_message` | Body / `args.description` |
| `sendmail_notification_log_type` | Notification Log `type` when intercepted from `send_notification_email` (`Assignment`, `Mention`, `Share`, `Energy Point`, `Alert`) |
| `sendmail_notification_log` | Notification Log row (`type`, `subject`, `email_content`, `from_user`, `for_user`, `document_type`, `document_name`) |
| `sendmail_from_user` | Full name of the user who triggered the log (`from_user`) |
| `sendmail_docinfo` | Document Follow digest |
| `sendmail_timeline` | Document Follow activity |
| `sendmail_workflow_actions` | Workflow action links |
| `sendmail_workflow_message` | Workflow body HTML |
| `sendmail_events` | Event Digest calendar rows |
| `alert` | The **Notification** definition |

Route recipients from the intercepted call override **Notification Recipient** rows.

## Configuration checklist

1. Sync custom fields (**Email Override** on **Notification**).
2. Create one **Notification** per intent × channel (e.g. Mention → Slack DM, Workflow Action → Email).
3. Set **Email Override** to the intended value; configure **Channel**, message template, webhook links.
4. **`document_type`** / **`event`** on override rows are not used for triggering — they remain for form layout only.
5. Put Jinja in **Message**, not **Subject**. Notification uses **Subject** as its title field; if someone assigns this Notification record, raw `{{ … }}` in Subject is inserted into Frappe’s stock assignment/share/mention sentences unchanged. Use **`{{ sendmail_subject }}`** in Message for the rendered desk notification text.
6. Restart workers after changes (cache is per-process).

## Example

**Mention → Email:**

- **Email Override:** `Mention, Assignment, Share, Energy Point, Alert`  
- **Channel:** Email  
- **Subject:** `{{ sendmail_subject }}`  
- **Message:** `{{ sendmail_message }}`

**Assignment vs Mention in one Slack DM Notification:**

```jinja
{% if sendmail_notification_log_type == "Assignment" %}
  {{ sendmail_subject }}
{% elif sendmail_notification_log_type == "Mention" %}
  {{ sendmail_from_user }} mentioned you: {{ sendmail_message | striptags }}
{% elif sendmail_notification_log_type == "Share" %}
  {{ sendmail_subject }}
{% else %}
  {{ sendmail_subject }}
{% endif %}
```

**Document Follow → Slack DM:**

- **Email Override:** Document Follow  
- **Channel:** Slack DM  
- **Subject:** plain text (e.g. `Document Follow`)  
- **Message:** use `sendmail_docinfo` and `sendmail_timeline` (see **Document Follow Override** installed by Communications, disabled by default)

**Workflow Action → Slack DM:**

- **Email Override:** Workflow Action  
- **Channel:** Slack DM  
- **Message:** `sendmail_workflow_message`, `sendmail_workflow_actions` (action links)

**Event Digest → Slack DM:**

- **Email Override:** Event Digest  
- **Channel:** Slack DM  
- **Message:** loop `sendmail_events` (`starts_on`, `subject`, `description`)

Starter rows (**Document Follow Override**, **Workflow Action Override**, **Event Digest Override**) are created on install with **`enabled = 0`**. Set **Channel**, webhook, enable, and adjust templates in Desk.

## Related

- [Sendmail call-site inventory](./sendmail-call-sites.md)
- [Desk notifications and chat integrations](./integrations.md)
