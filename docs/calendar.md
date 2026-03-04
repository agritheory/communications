<!-- Copyright (c) 2026, AgriTheory and contributors
For license information, please see license.txt-->

# Public Calendar Features

This module provides public calendar and scheduling features for the Communications app. It was migrated from the `public_calendar` app.

## Features

### Public Calendar DocType

The Public Calendar DocType allows users to create shareable calendars with configurable scheduling options.

**Key Fields:**
- `user` - The Frappe User whose events appear on this calendar
- `title` - Display name for the calendar
- `route` - URL-safe identifier for the calendar
- `is_public` - Makes the calendar visible at `/calendar`
- `allow_booking` - Enables the scheduling interface at- `enabled` - Master toggle

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

## Web Pages

### Calendar View (`/calendar`)

Displays events from Public Calendar records on a read-only calendar. Visitors can see when a user is busy without viewing event details.

**URLs:**
- `/calendar` - Shows all public calendars with a dropdown selector
- `/calendar?name=route` - Shows a specific calendar filtered by its Route field

### Schedule View (`/schedule`)

Interactive booking interface for appointments.

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

## Event Hooks

The module integrates with Frappe's Event DocType through document hooks:

- `on_update` - Detects cancellation or reschedule and sends notifications
- `on_trash` - Treats deletion as cancellation and sends notifications

## Scheduled Tasks

### Appointment Reminders

**Function:** `communications.communications.notifications.send_appointment_reminders`

**Schedule:** Hourly

Sends reminder notifications for upcoming appointments based on calendar settings.

## API Endpoints

### cancel_appointment

**Method:** `communications.communications.communications.api.cancel_appointment`

**Parameters:**
- `event` (str) - Event document name
- `reason` (str, optional) - Cancellation reason

**Returns:**
```json
{
	"status": "success",
	"message": "Appointment cancelled"
}
```

## Custom Fields

### Event Participants - RSVP Field

Adds an `rsvp` Select field to the Event Participants child table with options:
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

## Migration Notes

This module was migrated from the `public_calendar` app. All import paths have been updated from `public_calendar.*` to `communications.communications.*`.

### Key File Locations

| Original Path | New Path |
|--------------|----------|
| `public_calendar.public_calendar.ics` | `communications.communications.ics` |
| `public_calendar.public_calendar.notifications` | `communications.communications.notifications` |
| `public_calendar.public_calendar.overrides.event` | `communications.communications.overrides.event` |
| `public_calendar.www.calendar` | `communications.communications.www.calendar` |
| `public_calendar.www.schedule` | `communications.communications.www.schedule` |
| `public_calendar.www.rsvp` | `communications.communications.www.rsvp` |
