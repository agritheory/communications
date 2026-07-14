<!-- Copyright (c) 2026, AgriTheory and contributors
For license information, please see license.txt-->

# Video Conferencing

<div class="byline">
  Tyler Matteson 2026-06-24
</div>


This app adds optional video meeting support on the **Event** doctype. It is separate from the **Public Calendar** booking flow: public bookings do not set a video provider automatically.

## Appointment Settings

Single DocType **Appointment Settings** (Communications module) holds integration toggles and credentials.

### Zoom

When **Enable Zoom** is checked, configure Server-to-Server OAuth:

- Account ID, Client ID, Client Secret (secret stored as password)
- **Default Zoom User Email** — Zoom user on whose account meetings are created

The app caches an access token in **Zoom Access Token** (hidden); it is refreshed when missing or after API `401` responses.

The Zoom integration reads **`event.zoom_user_email`** when present (add a custom **Data** field on **Event** if you want a per-event host override); otherwise it uses **Appointment Settings** → Default Zoom User Email.

### Google Meet (Communications provider)

**Enable Google Meet** turns on the Communications **Google Meet** provider. The in-app implementation only builds a `conferenceData` payload suitable for the Google Calendar API; it **does not** call Google. **`video_conference_url`** and **`video_conference_meeting_id`** stay empty for this provider unless you extend the integration.

The HTML note on the form is accurate: for real Meet links you should rely on **Frappe’s Google Calendar integration** (see below).

## Event custom fields (Communications)

| Field | Purpose |
| ----- | ------- |
| **Video Conference Provider** | `None`, `Zoom`, or `Google Meet` |
| **Meeting ID** | Provider meeting id (hidden); set for Zoom after create |
| **Meeting URL** | Join URL (read only); appended to description when present |
| **Meeting Data** | JSON payload from the provider (hidden) |

## How hooks run

`hooks.py` registers **Event** document hooks on the Communications override module:

- **`validate`** — runs `handle_video_conference`: creates or updates Zoom meetings when the provider is enabled in Appointment Settings; stores id/url/data on the Event and appends the join link to **Description** when a URL exists.
- **`on_trash`** — runs `delete_video_conference` (e.g. Zoom API delete) before other trash logic.

Frappe core still registers its own **Event** hooks for **Google Calendar** (`after_insert` / `on_update` / `on_trash`) in `frappe/hooks.py`. Those are independent of Communications’ `validate` hook.

## Frappe Google Calendar + Meet (recommended for Google)

Core Frappe provides:

- **`sync_with_google_calendar`**, **`google_calendar`**, **`google_calendar_id`**, etc.
- **`add_video_conferencing`** — sends `conferenceData` to Google when pushing an Event and stores **`google_meet_link`** (`hangoutLink`).

That path **does not** use Communications’ **Video Conference Provider** select. In practice:

- **Zoom** — use Communications **Video Conference Provider = Zoom** + Appointment Settings.
- **Google Meet** — use Frappe’s **Sync with Google Calendar** + **Add video conferencing**, or extend Communications to bridge its **Google Meet** option to that flow.

## Related

- [Public Calendar](./public_calendar.md)
