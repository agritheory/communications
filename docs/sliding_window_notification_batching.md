<!-- Copyright (c) 2026, AgriTheory and contributors
For license information, please see license.txt-->

# Sliding Window Notification Batching

<div class="byline">
  Francisco Roldan 2026-06-10
</div>

The **Sliding Window Notification Batching** feature collects assignment notifications over a configurable time window and delivers them as a single batched email digest instead of sending individual emails for each assignment. This reduces notification fatigue and respects user delivery hours.

## Overview

When a user receives multiple assignments in a short period, instead of flooding their inbox with separate emails, the system:

1. Queues each assignment notification
2. Groups them into a time-based **window** (default: 15 minutes)
3. Sends a single **digest email** containing all assignments when the window expires
4. Respects configurable **delivery hours** so digests are not sent outside working hours

## Configuration

Enable and configure the feature via the **Notification Window Settings** DocType.

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | Yes | Master toggle for notification batching |
| `collection_window_minutes` | 15 | Minutes to collect notifications before dispatching |
| `max_digest_size` | 50 | Maximum assignments in a single digest email |
| `delivery_start_hour` | 8 | Start of delivery window (24-hour format) |
| `delivery_end_hour` | 20 | End of delivery window (24-hour format) |
| `time_zone` | UTC | Timezone for delivery hour calculations |
| `bypass_batching_for_priority` | No | If enabled, priority DocTypes skip batching and send immediately |
| `priority_doctypes` | _(empty)_ | Comma-separated list of DocTypes to bypass batching |
| `batch_template` | _(default)_ | Custom Email Template for batch digests |
| `individual_template` | _(default)_ | Custom Email Template for bypassed individual notifications |


## How It Works

### 1. Assignment Interception

When a user is assigned a document (via `frappe.desk.form.assign_to.add`), the override in `communications/overrides/assignment.py` intercepts the call:

- If **Notification Window Settings** is **disabled**, the standard Frappe notification is sent.
- If **enabled**, an **Assignment Notification Queue** record is created with status **Queued** instead of sending an immediate notification.

### 2. Window Management

The `WindowManager` class (`window_manager.py`) uses **Redis** to track sliding windows per user:

- A **window key** is generated in the format `{user}_{YYYYMMDD_HHMMSS}`.
- Each window has a `window_start` and `window_end` based on `collection_window_minutes`.
- Notifications arriving within the same window share the same `window_key`.
- A `notification_count` is maintained in Redis for each window.

### 3. Scheduled Processing

A **cron job** runs every minute (`* * * * *`) via `process_notification_windows()` in `background_jobs.py`. It calls `BatchProcessor.process_expired_windows()` to find windows whose `window_end` has passed.

### 4. Batch Processing

For each expired window, `BatchProcessor` (`batch_processor.py`):

1. Fetches all queued notifications for that user/window from the database.
2. Separates notifications into:
   - **Bypass notifications** (priority DocTypes) — sent individually via `Dispatcher.send_individual_notification()`.
   - **Batch notifications** — processed as a digest.
3. Checks **delivery hours**:
   - **Within delivery hours**: `DigestBuilder` groups notifications by DocType, builds an HTML digest, and `Dispatcher.send_digest()` sends the email. Queue entries are marked **Sent**.
   - **Outside delivery hours**: Notifications are **rescheduled** — a new `window_key` is assigned pointing to the next delivery window, and status remains **Queued**.

### 5. Digest Building

The `DigestBuilder` (`digest_builder.py`):

- Groups notifications by `reference_doctype`.
- Generates report URLs for each group.
- Renders HTML using either a custom email template (if configured) or a default monospace-styled template.
- Respects `max_digest_size` by chunking large batches into multiple digests.

## Delivery Restrictions

The `DeliveryRestrictions` class handles timezone-aware delivery hour checks:

- Uses the global `time_zone` from settings, or a **user-specific timezone** from the User profile if set.
- Supports **overnight windows** (e.g., `delivery_start_hour=22`, `delivery_end_hour=6`).
- When rescheduling, calculates the next valid delivery window start time.

## Queue Lifecycle

**Assignment Notification Queue** entries follow this lifecycle:

```
Queued --> Sent        (digest or individual sent successfully)
     \--> Failed       (send error)
     \--> Rescheduled  (outside delivery hours, new window_key assigned)
```

### Cleanup

A daily scheduled task (`cleanup_old_queue_entries()`) removes **Sent** and **Failed** entries older than **30 days** to prevent database bloat.

## Email Override Integration

The sliding window notification system integrates with the **Email Override** feature (documented in [sendmail-routes.md](./sendmail-routes.md)) to route assignment notifications through configured **Notification** records.

### How it works

When a **Notification** record is configured with **Email Override** set to `Mention, Assignment, Share, Energy Point, Alert`, the `Dispatcher` class checks for this override before sending emails:

1. **Digest emails**: When `Dispatcher.send_digest()` is called, it constructs kwargs with the digest subject and HTML content, then calls `try_email_override()` with the assigned **User** as the context document. If an override exists, the digest is routed through the Notification's configured channel (Email, Slack DM, Teams DM, etc.).

2. **Individual notifications**: When `Dispatcher.send_individual_notification()` is called (for priority bypass notifications), it constructs kwargs with the assignment subject and message, then calls `try_email_override()` with the referenced business document as the context. If an override exists, the notification is routed through the Notification's configured channel.

3. **Fallback**: If no email override is configured, the system falls back to direct `frappe.sendmail` calls as before.

### Template variables

When routed through an email override, the following template variables are available in the Notification's **Message** field:

| Variable | Description |
|----------|-------------|
| `sendmail_subject` | The digest or individual assignment subject |
| `sendmail_message` | The digest HTML or individual notification body |
| `sendmail_notification_log_type` | Always `"Assignment"` for batched notifications |
| `sendmail_notification_log` | Dict with `type`, `subject`, `email_content`, `from_user`, `for_user`, `document_type`, `document_name` |
| `sendmail_from_user` | Full name of the user who made the assignment |

### Configuration example

To route assignment digests to Slack DM:

1. Create a **Notification** record:
   - **Email Override**: `Mention, Assignment, Share, Energy Point, Alert`
   - **Channel**: Slack DM
   - **Slack Webhook URL**: (select your Slack webhook)
   - **Subject**: `Assignment Digest`
   - **Message**: 
     ```jinja
     {% if sendmail_notification_log_type == "Assignment" %}
     {{ sendmail_from_user }} assigned you new tasks:
     {{ sendmail_message | striptags }}
     {% endif %}
     ```
   - **Enabled**: Yes

2. Enable **Notification Window Settings** with your desired collection window and delivery hours.

Assignment notifications will now be batched and delivered as Slack DMs instead of emails.

## Architecture

```
User Assignment
       |
       v
[overrides/assignment.add()] -- checks NotificationWindowSettings.enabled
       |
       +-- Disabled --> frappe.desk.form.assign_to.notify_assignment() (standard)
       |
       +-- Enabled --> queue_assignment_notification()
                            |
                            v
                    [Assignment Notification Queue] (DB)
                            |
                            +-- bypass_batching=1 --> Dispatcher.send_individual_notification()
                            |
                            +-- bypass_batching=0 --> WindowManager.generate_window_key()
                                                         |
                                                         v
                                                  [Redis: assignment_notification_window:{user}]
                                                         |
                                                         v
                                                  (window collects notifications for N minutes)
                                                         |
                                                         v
                    [cron: * * * * *] --> process_notification_windows()
                                              |
                                              v
                                    BatchProcessor.process_expired_windows()
                                              |
                              +---------------+---------------+
                              |                               |
                    Within Delivery Hours            Outside Delivery Hours
                              |                               |
                              v                               v
                    DigestBuilder.build_digest()      reschedule_notifications()
                              |                       (new window_key, next day)
                              v
                    Dispatcher.send_digest()
                              |
                              v
                    Update queue status --> Sent/Failed
                    WindowManager.clear_window()
```