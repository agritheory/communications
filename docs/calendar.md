<!-- Copyright (c) 2026, AgriTheory and contributors
For license information, please see license.txt-->

# Public Calendar Features

<div class="byline">
  Tyler Matteson 2026-06-02
</div>


This module provides public calendar and scheduling features for the Communications app. It was migrated from the `public_calendar` app.

## Features

### Public Calendar DocType

The Public Calendar DocType allows users to create shareable calendars with configurable scheduling options.

**Key Fields:**
- `user` - The Frappe User whose events appear on this calendar
- `title` - Display name for the calendar
- `route` - URL-safe identifier for the calendar
- `is_public` - Makes the calendar visible at `/calendar`
- `allow_booking` - Enables the scheduling interface at `/schedule`
- `enabled` - Master toggle

**Scheduling Configuration:**
- `slot_duration` - Length of each bookable time slot (minutes)
- `buffer_time` - Required gap between appointments (minutes)
- `min_notice_hours` - How far in advance appointments must be booked
- `max_advance_days` - How far into the future appointments can be booked
- `max_meeting_duration` - Maximum appointment length
- `working_hours` - JSON configuration of available hours per day

**Notification Settings:**
- `notify_host_on_booking` - Send confirmation to calendar owner
- `notify_guest_on_booking` - Send confirmation to the person who booked
- `notify_on_cancellation` - Send cancellation notices
- `send_reminder` - Enable reminder notifications before appointments
- `reminder_minutes_before` - How many minutes before to send reminders

**Per-calendar Notification templates (Link → Notification):**
- `host_booking_notification` - Email sent to the host on booking (when enabled)
- `booker_booking_notification` - Email sent to the guest on booking (when enabled)
- `cancellation_notification` - Cancellation template
- `reschedule_notification` - Reschedule template
- `reminder_notification` - Reminder template

If unset, the code falls back to the default **Notification** record names created on install (see Installation).

## Web Pages

### Calendar View (`/calendar`)

Displays events from Public Calendar records on a read-only calendar. Visitors can see when a user is busy without viewing event details.

**URLs:**
- `/calendar` - Shows all public calendars with a dropdown selector
- `/calendar?name=route` - Shows a specific calendar filtered by its Route field

### Schedule View (`/schedule`)

Interactive booking interface for appointments.

**Authentication:** The schedule page and booking APIs require a logged-in user. **Guest** receives a not-found response (no public guest booking).

**URLs:**
- `/schedule` - Lists all calendars that accept bookings
- `/schedule?name=route` - Opens the booking interface for a specific calendar

### RSVP Page (`/rsvp`)

Processes RSVP actions from email links with secure HMAC tokens.

**Query Parameters:**
- `event` - Event document name
- `email` - Recipient's email address
- `action` - One of: `confirm`, `decline`, `cancel`
- `token` - HMAC verification token

## Notifications

### Notification Types

| Type | Trigger | Recipients |
|------|---------|------------|
| Booking Confirmation | New appointment created | Host and/or guest based on settings |
| Cancellation | Appointment cancelled or declined | All participants except the person who cancelled |
| Reschedule | Appointment time changed | All participants except the person who rescheduled |
| Reminder | Scheduled time before appointment | Host and guest |

### Template Variables

Notification templates have access to these Jinja variables:

**Event Information:**
- `subject` - Event subject line
- `description` - Event description
- `starts_on` - Start datetime object
- `ends_on` - End datetime object
- `starts_on_formatted` - Formatted start date
- `start_time_formatted` - Formatted start time
- `end_time_formatted` - Formatted end time
- `duration_minutes` - Appointment length in minutes

**Participant Information:**
- `host_name` - Full name of the calendar owner
- `host_email` - Email address of the calendar owner
- `guest_name` - Full name of the primary guest
- `guest_email` - Email address of the primary guest
- `guests` - List of all guest participants
- `is_host` - Boolean indicating if recipient is the host
- `recipient_email` - Email address of the current recipient

**Action URLs:**
- `confirm_url` - Link to confirm attendance
- `decline_url` - Link to decline the invitation
- `cancel_url` - Link to cancel the appointment

## ICS Calendar Attachments

Email notifications include ICS (iCalendar) file attachments that can be imported into calendar applications like Outlook, Google Calendar, and Apple Calendar.

**ICS Methods:**
- `REQUEST` - New invitation or update
- `CANCEL` - Appointment cancellation

## Event integration

### Linking Events to a Public Calendar

Bookings created from `/schedule` set **`reference_doctype`** = `Public Calendar` and **`reference_docname`** to the calendar’s name (same as its **route** / autoname). Notifications and RSVP logic use this link to load **Public Calendar** settings.

### Document hooks (Communications)

Registered on **Event** in `hooks.py`:

- **`validate`** - Video conferencing (Zoom / Communications Google Meet provider). See [Video conferencing](./video-conferencing.md).
- **`on_update`** - If the Event is tied to a Public Calendar: detects **cancel** or **reschedule** (time change) and sends the appropriate notifications.
- **`on_trash`** - Deletes provider meetings when configured, then sends cancellation notifications for Public Calendar events when settings allow.

Frappe core may also run **Event** hooks for **Google Calendar** sync; that pipeline is separate from Public Calendar notifications.

## Website / Jinja

`hooks.py` registers these methods for use in website templates (e.g. **Notification** HTML):

- `communications.communications.public_calendar_notifications.rsvp_confirm_url`
- `communications.communications.public_calendar_notifications.rsvp_decline_url`
- `communications.communications.public_calendar_notifications.rsvp_cancel_url`

## Scheduled Tasks

### Appointment Reminders

**Function:** `communications.communications.public_calendar_notifications.send_appointment_reminders`

**Schedule:** Hourly

Sends reminder notifications for upcoming appointments based on calendar settings.

## Whitelisted API methods

Call these with `POST /api/method/...` (and a valid session / CSRF as usual).

### Calendar view (read-only busy times)

| Method | Guest allowed | Description |
| ------ | ------------- | ----------- |
| `communications.www.calendar.index.get_events` | Yes | Busy slots for public calendars (`is_public`); optional `public_calendar` filter |

### Schedule / booking (authenticated)

| Method | Guest allowed | Description |
| ------ | ------------- | ----------- |
| `communications.www.schedule.index.get_events` | Yes | Availability-style events for a bookable calendar (`allow_booking`) |
| `communications.www.schedule.index.book_appointment` | No | Creates **Event**, participants, sends booking notifications |
| `communications.www.schedule.index.get_available_timezones` | No | IANA timezones for the picker |
| `communications.www.schedule.index.update_my_timezone` | No | Saves **User** `time_zone` |

The schedule **`get_events`** method is whitelisted for **Guest**; the **`/schedule`** web page still requires login, so availability is not exposed through that route to anonymous visitors.

### Cancel appointment

**Method:** `communications.communications.communications.api.cancel_appointment`

**Parameters:**
- `event` (str) - Event document name
- `reason` (str, optional) - Cancellation reason

**Auth:** Caller must be an **Event Participant** linked to **User** = session user, or hold **Event** delete permission.

**Returns:**
```json
{
	"status": "success",
	"message": "Appointment cancelled"
}
```

## Custom Fields

### Event — video conferencing

Communications adds **Video Conference Provider**, **Meeting ID**, **Meeting URL**, and **Meeting Data** on **Event**. See [Video conferencing](./video-conferencing.md).

### Event Participants — RSVP

Adds an **`rsvp`** Select field to the Event Participants child table with options:

- Pending
- Accepted
- Declined
- Cancelled

## Installation

Default notifications are created automatically during app installation:
- Public Calendar - Booking Confirmation
- Public Calendar - Cancellation
- Public Calendar - Reschedule
- Public Calendar - Reminder

## Other app behavior

- **Notification DocType** — class override `CommunicationsNotification` (see `hooks.py` → `override_doctype_class`).
- **Desk assignment emails** — configure a **Notification** with **Email Override** = **Assignment** to route assignment Notification Log email to Slack DM, Teams DM, etc. See [Email Override](./sendmail-routes.md).

## Migration Notes

This module was migrated from the `public_calendar` app. Python modules under the inner package use the `communications.communications.*` prefix; **website** modules live at `communications.www.*` (same pattern as a standard Frappe app).

### Key file locations

| Original (`public_calendar` app) | Current (`communications` app) |
| ------------------------------- | ------------------------------ |
| `public_calendar.public_calendar.ics` | `communications.communications.ics` |
| `public_calendar.public_calendar.notifications` | `communications.communications.public_calendar_notifications` |
| `public_calendar.public_calendar.overrides.event` | `communications.communications.overrides.event` |
| `public_calendar.www.calendar` | `communications.www.calendar` |
| `public_calendar.www.schedule` | `communications.www.schedule` |
| `public_calendar.www.rsvp` | `communications.www.rsvp` |
| `public_calendar.public_calendar.api` (if used) | `communications.communications.communications.api` |

## Related documentation

- [Video conferencing and Appointment Settings](./video-conferencing.md)
- [Desk notifications and chat integrations](./integrations.md)
