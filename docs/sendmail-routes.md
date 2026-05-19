<!-- Copyright (c) 2026, AgriTheory and contributors
For license information, please see license.txt-->

# Sendmail route overrides

<div class="byline">
  Tyler Matteson 2026-05-19
</div>

On app import, **`communications/__init__.py`** patches **`frappe.sendmail`** so selected outbound emails can be handled by **Notification** records (via **`CommunicationsNotification`**) instead of Frappe’s default email path.

This document defines what **`send_notification_email`** covers, how routing works, and what is **not** intercepted.

## What `send_notification_email` is

In Frappe core, **`send_notification_email`** lives in:

`frappe/desk/doctype/notification_log/notification_log.py`

It is the **only** function that sends email for desk **Notification Log** rows. It is called from **`NotificationLog.after_insert`** when the recipient has email enabled for that log type (see **Notification Settings** per user).

Flow:

1. Something in desk creates a **Notification Log** (usually via **`enqueue_create_notification`**).
2. The log is inserted for each target user.
3. If email is enabled for that log’s **`type`**, **`send_notification_email(notification_log_doc)`** runs.
4. That function calls **`frappe.sendmail`** with template **`new_notification`**, passing the referenced document in **`args.document_type`** / **`args.document_name`** and HTML body in **`args.description`**.

Communications wraps step 4: before **`sendmail`**, we set **`frappe.local.sendmail_route_context`** with **`notification_log_type`** and **`template`**, so **Notification** rows can filter by mention vs assignment vs share, etc.

## Scope: Notification Log `type` values

All of the following share the **same call site** (`send_notification_email`). They differ by **`Notification Log.type`** (use **`sendmail_route_match`** to route separately).

| `type` | Typical trigger | Email content notes |
|--------|-----------------|---------------------|
| **Mention** | `@` mention in a **Comment** (`notify_mentions` in `frappe/desk/notifications.py`) | `email_content` = comment HTML |
| **Assignment** | Document assignment (`notify_assignment` in `frappe/desk/form/assign_to.py`), unless overridden by communications assignment patch | Subject describes assignment |
| **Share** | Document shared (`frappe/share.py`) | |
| **Energy Point** | Energy point award (`energy_point_log.py`) | Skipped if `email_content` is `None` |
| **Alert** | e.g. submission queue, prepared report, **Notification** “System Notification” | Various desk/system alerts |
| *(empty)* | Rare; treated as `""` in match | |

**Not** in this path:

- Password reset / welcome / login mail (**`User.send_login_mail`** and other **`User`** call sites)
- **Notification** DocType event emails (**`Notification.send_an_email`** — different `frappe.sendmail` caller)
- Newsletters, auto email reports, contact form, 2FA OTP, backup emails, etc.

Those use other modules/functions. They are **not** intercepted unless you add their **`sendmail_route_key`** to a **Notification** on purpose.

## Supported sendmail route call sites

Besides Notification Log email, communications supports routing these Frappe call sites when matching **Notification** rows exist in the database (configure in Desk; test fixtures use **`communications/tests/setup.py`**):

### Workflow action email

| | |
|--|--|
| **Function** | `send_workflow_action_email` in `frappe/workflow/doctype/workflow_action/workflow_action.py` |
| **Route key** | `('frappe.workflow.doctype.workflow_action.workflow_action', 'send_workflow_action_email')` |
| **Typical match** | `{"template": "workflow_action"}` |
| **Trigger** | Workflow transition requires approval; email sent to users with permission to act |
| **Reference document** | Workflow document (`reference_doctype` / `reference_name` on `sendmail`) |
| **Recipients** | Per-approver email from `sendmail` kwargs |
| **Extra template data** | `sendmail_workflow_actions`, `sendmail_workflow_message` (from `args.actions` / `args.message`) |
| **Attachments** | PDF print of the document (forwarded via `sendmail_route_attachments`) |

### Document Follow digest

| | |
|--|--|
| **Function** | `send_email_alert` in `frappe/desk/form/document_follow.py` |
| **Route key** | `('frappe.desk.form.document_follow', 'send_email_alert')` |
| **Typical match** | `{"template": "document_follow"}` |
| **Trigger** | Scheduled job `send_document_follow_mails` (hourly/daily/weekly per user setting) |
| **Reference document** | **First** entry in `args.docinfo` (`reference_doctype` / `reference_docname`). Multi-document digests still use one `doc` for Notification context; use `sendmail_docinfo` and `sendmail_timeline` in the template for the full digest. |
| **Recipients** | Following user's email |
| **Extra template data** | `sendmail_docinfo`, `sendmail_timeline` |

If `docinfo` is empty, routing does not run (falls through to original `frappe.sendmail`).

### Document Follow prerequisites (Frappe core)

Creating a row in **Document Follow** is **not** handled by the communications sendmail route. Frappe’s `follow_document` in `frappe/desk/form/document_follow.py` returns without saving when any of these apply:

| Condition | Result |
|-----------|--------|
| Doctype is in the hardcoded blocklist (`ToDo`, `Comment`, `Communication`, `File`, …) | No row created |
| Doctype does not have **Track Changes** enabled | No row created |
| User is **Administrator** | No row created |
| User does not have **Send Notifications For Documents Followed By Me** (`document_follow_notify`) enabled | No row created |
| Already following | No new row (existing row kept) |

**ToDo cannot be followed** in stock Frappe (it is on the blocklist). A Notification with `document_type: ToDo` is only a template context default; test Document Follow on e.g. **Event**, **Sales Order**, or any submittable doc with **Track Changes**.

The sidebar **Follow** button (`update_follow`) updates the UI even when `follow_document` returns nothing — check the **Document Follow** list to confirm a row was created.

## How routing works

The sendmail route **cache is built from enabled Notification records** on first intercepted `frappe.sendmail` in a process (`build_sendmail_cache()`). Nothing is pre-seeded in application code; route keys and matches are site configuration.

### 1. `sendmail_route_key` (required to participate)

Python tuple literal: **`(module_name, function_name)`**, matching the **immediate caller** of **`frappe.sendmail`** (stack depth 2 from the patch).

Notification Log emails:

```python
('frappe.desk.doctype.notification_log.notification_log', 'send_notification_email')
```

### 2. `sendmail_route_match` (optional filter)

JSON object. **Every key must equal** the route context for that **`sendmail`** call. If blank, the **Notification** matches **all** calls at that route key (usually too broad for `send_notification_email`).

Examples:

```json
{"notification_log_type": "Mention"}
```

```json
{"notification_log_type": "Assignment"}
```

```json
{"notification_log_type": "Share", "template": "new_notification"}
```

`template` is always **`new_notification`** for this call site; including it is optional but documents intent.

### 3. Reference document and recipients

When a route matches, the patch:

- Loads **`doc`** = **`frappe.get_doc(document_type, document_name)`** from **`reference_*`** kwargs or **`args.document_*`** (the **business document** the log points at, e.g. **ToDo**, **Sales Order** — not **Notification Log** or **Comment**).
- Passes **`recipients`**, **`subject`**, and body (from **`args.description`** for template-based sends) into **`CommunicationsNotification`** as **`sendmail_route_*`** locals for templates and channel handlers.

Jinja context for routed sends:

| Variable | Source |
|----------|--------|
| `doc` | Referenced document |
| `sendmail_subject` | Original `sendmail` subject |
| `sendmail_message` | `kwargs.message` or `args.description` (comment HTML for mentions) |
| `sendmail_docinfo` | Document Follow: list of followed documents |
| `sendmail_timeline` | Document Follow: activity lines |
| `sendmail_workflow_actions` | Workflow: possible actions (name + link) |
| `sendmail_workflow_message` | Workflow: body HTML from the original email |
| `alert` | The **Notification** definition |

Example mention **Message** field: `{{ sendmail_message }}`  
Example mention **Subject** field: `{{ sendmail_subject }}`

**Notification Recipient** rows (`receiver_by_document_field`, etc.) are **ignored** when route recipients are present; the mentioned user’s email comes from the intercepted **`sendmail`** call.

### 4. Re-entry guard

While **`CommunicationsNotification`** sends email, it calls **`frappe.sendmail`** again. **`frappe.local.in_sendmail_route`** forces those calls through to the **original** `sendmail` so routing does not loop.

## Multiple Notification rows at one call site

Several enabled **Notification** records may share the same **`sendmail_route_key`**. Each whose **`sendmail_route_match`** passes will run **`Notification.send`** for the same event.

- Use this for multiple channels (e.g. Email + Slack DM) with the **same** match.
- Avoid overlapping matches (e.g. one row with **empty** match and another with **`Mention`**) unless you intend **both** to fire.

## Assignment vs Notification Log route

**ToDo assignment** can be handled two ways in this app:

1. **Assignment patch** (`custom_notify_assignment`): uses a **Notification** with **Document Type** = **ToDo** and **Event** = **Save** (no sendmail route).
2. **Notification Log** route: Frappe’s default assignment path still creates **`type: Assignment`** logs; **`send_notification_email`** can route those if configured.

Do not assume both paths are active; check which patch/configuration is enabled for your site.

## Configuration checklist

1. Migrate/sync custom fields (**Sendmail Route Key**, **Sendmail Route Match** on **Notification**).
2. Create one **Notification** per behavior (mention, assignment log email, etc.).
3. Set **`sendmail_route_key`** to the tuple above for desk log emails.
4. Set **`sendmail_route_match`** so each row only handles the intended **`notification_log_type`**.
5. Use **`sendmail_subject`** / **`sendmail_message`** in templates where the original email body matters (especially **Mention**).
6. Restart workers / clear cache after changing route keys (cache is built on first routed `sendmail` in a process).

## Example Notification configuration

**Workflow:**

```python
sendmail_route_key = "('frappe.workflow.doctype.workflow_action.workflow_action', 'send_workflow_action_email')"
sendmail_route_match = '{"template": "workflow_action"}'
```

**Document Follow:**

```python
sendmail_route_key = "('frappe.desk.form.document_follow', 'send_email_alert')"
sendmail_route_match = '{"template": "document_follow"}'
```

## Tests and fixtures

- **`communications/tests/test_sendmail_override.py`** — cache, call-site identity, routing, match filtering, workflow and document-follow reference resolution.
- **`communications/tests/setup.py`** — `create_sendmail_route_notifications()` installs example rows (Mention, Assignment, Workflow, Document Follow).

## Related

- [Desk notifications and chat integrations](./integrations.md)
- [Public Calendar Features](./calendar.md)
