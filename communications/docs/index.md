<!-- Copyright (c) 2026, AgriTheory and contributors
For license information, please see license.txt-->

# Communications Documentation

<div class="byline">
  Tyler Matteson 2026-06-24
</div>


Communications is a Frappe app that brings **scheduling, messaging, and signing** into the same system where your business data lives. Instead of bolting on separate calendaring, notification, or e-sign tools, it extends ERPNext and HRMS so people can book appointments, receive desk alerts, and complete signatures without leaving the ERP context.

## Who it is for

- **Site administrators** who configure Slack, Teams, Zoom, notification routing, and portal access
- **Operations and HR teams** who share bookable calendars, run appointment workflows, and send documents for signature
- **Developers and implementers** building on Frappe who need whitelisted APIs, document hooks, and modular features they can enable per site

Communications is a collection of **optional, modular features** — not a single end-to-end workflow. Install the app, then turn on and configure only what your site needs.

## Features

- **[Public Calendar](./public_calendar.md)**: shareable calendars, booking, RSVP, ICS attachments, and appointment notifications
- **[Video Conferencing](./video_conferencing.md)**: Zoom and Google Meet on **Event** via **Appointment Settings**
- **[Notification Channels](./notification_channels.md)**: Slack DM and Teams DM on **Notification**
- **[Slack DM Setup](./slack_setup.md)**: Bot token and **Slack Webhook URL** configuration
- **[Teams DM Setup](./teams_setup.md)**: Azure Bot and Entra app for Teams direct messages
- **[Email Override](./email_override.md)**: intercept stock Frappe emails via **Notification**
- **[Assignment Notification Batching](./notification_batching.md)**: sliding-window digest emails for assignments
- **[Electronic Signature](./electronic_signature.md)**: multi-signer workflow and portal signing
- **[Phone Helpers](./phone_helpers.md)**: desk phone field formatting and call button

## Installation

Full [installation instructions](https://github.com/agritheory/communications#install-instructions) are on the application repository.

Communications requires **ERPNext** and **HRMS** (`required_apps` in `hooks.py`).
