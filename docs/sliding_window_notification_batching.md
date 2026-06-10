<!-- Copyright (c) 2026, AgriTheory and contributors
For license information, please see license.txt-->

# Sliding Window Notification Batching

<div class="byline">
  Feature documentation 2026-06-10
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