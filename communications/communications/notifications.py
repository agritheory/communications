# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

"""
Notification utilities for Public Calendar.

Handles notifications via Frappe's Notification DocType for bookings,
cancellations, and reminders. Supports multiple channels (Email, Slack,
System Notification, SMS). Includes HMAC-based token generation for
secure guest RSVP actions.

Terminology:
- Host: The user linked in Public Calendar.user field (whose calendar is being booked)
- Guest: Any other participant in the event (the person making the booking)
"""

import hashlib
import hmac
from typing import Literal

import frappe
from frappe.exceptions import OutgoingEmailError
from frappe.query_builder import DocType
from frappe.utils import add_to_date, format_datetime, get_datetime, get_url, now_datetime

from communications.communications.ics import generate_ics_attachment


def generate_rsvp_token(
	event_name: str,
	email: str,
	action: Literal["confirm", "decline", "cancel"],
) -> str:
	"""
	Generate a deterministic HMAC token for RSVP actions.

	Token is derived from event name, email, action, and site secret.
	No database storage required - token can be verified by regenerating.
	"""
	secret = frappe.local.conf.get("secret_key") or frappe.local.site
	message = f"{event_name}:{email}:{action}"
	return hmac.new(
		secret.encode(),
		message.encode(),
		hashlib.sha256,
	).hexdigest()[:32]


def verify_rsvp_token(
	event_name: str,
	email: str,
	action: Literal["confirm", "decline", "cancel"],
	token: str,
) -> bool:
	"""Verify an RSVP token."""
	expected = generate_rsvp_token(event_name, email, action)
	return hmac.compare_digest(expected, token)


def get_rsvp_url(
	event_name: str,
	email: str,
	action: Literal["confirm", "decline", "cancel"],
) -> str:
	"""Generate a full RSVP URL for an action."""
	token = generate_rsvp_token(event_name, email, action)
	base_url = get_url()
	return f"{base_url}/rsvp?event={event_name}&email={email}&action={action}&token={token}"


def get_public_calendar_for_event(event: "frappe.Document") -> "frappe.Document | None":
	"""Get the Public Calendar linked to an event via ref_type/ref_name."""
	if event.get("reference_doctype") == "Public Calendar" and event.get("reference_docname"):
		return frappe.get_doc("Public Calendar", event.reference_docname)
	return None


def get_host_and_guests(
	event: "frappe.Document",
	public_calendar: "frappe.Document",
) -> tuple[dict | None, list[dict]]:
	"""
	Identify host and guests from event participants.

	Host is the participant matching Public Calendar.user.
	Guests are all other participants.

	Returns:
	        tuple of (host_dict, list_of_guest_dicts)
	        Each dict has keys: user, email, full_name
	"""
	host = None
	guests = []

	calendar_user = public_calendar.user

	for p in event.event_participants or []:
		if p.reference_doctype != "User":
			continue

		user_data = frappe.db.get_value(
			"User",
			p.reference_docname,
			["name", "email", "full_name"],
			as_dict=True,
		)
		if not user_data:
			continue

		participant_info = {
			"user": user_data.name,
			"email": user_data.email,
			"full_name": user_data.full_name,
		}

		if p.reference_docname == calendar_user:
			host = participant_info
		else:
			guests.append(participant_info)

	return host, guests


def _build_notification_context(
	event: "frappe.Document",
	public_calendar: "frappe.Document",
	host: dict,
	guests: list[dict],
	recipient_email: str,
) -> dict:
	"""Build context dict for notification templates."""
	starts_on = get_datetime(event.starts_on)
	ends_on = get_datetime(event.ends_on) if event.ends_on else None

	# For backwards compatibility and simpler templates, expose first guest as primary
	primary_guest = guests[0] if guests else {}

	is_host = recipient_email == host.get("email")

	return {
		"event": event,
		"event_name": event.name,
		"subject": event.subject,
		"description": event.description,
		"starts_on": starts_on,
		"ends_on": ends_on,
		"starts_on_formatted": format_datetime(starts_on, "EEEE, MMMM d, yyyy"),
		"start_time_formatted": format_datetime(starts_on, "h:mm a"),
		"end_time_formatted": format_datetime(ends_on, "h:mm a") if ends_on else None,
		"duration_minutes": int((ends_on - starts_on).total_seconds() / 60) if ends_on else None,
		"calendar": public_calendar,
		"calendar_title": public_calendar.title,
		# Host info
		"host_name": host.get("full_name"),
		"host_email": host.get("email"),
		# Primary guest info (for simple templates)
		"guest_name": primary_guest.get("full_name"),
		"guest_email": primary_guest.get("email"),
		# All guests (for advanced templates)
		"guests": guests,
		# Recipient context
		"is_host": is_host,
		"recipient_email": recipient_email,
		# RSVP URLs
		"confirm_url": get_rsvp_url(event.name, recipient_email, "confirm"),
		"decline_url": get_rsvp_url(event.name, recipient_email, "decline"),
		"cancel_url": get_rsvp_url(event.name, recipient_email, "cancel"),
		"site_url": get_url(),
	}


def _get_ics_attachment_for_email(
	event: "frappe.Document",
	host: dict,
	guests: list[dict],
	method: Literal["REQUEST", "CANCEL"] = "REQUEST",
	sequence: int = 0,
) -> dict:
	"""Generate ICS attachment for email notifications."""
	attendees = [
		{
			"email": host["email"],
			"name": host["full_name"],
			"status": "ACCEPTED" if method == "REQUEST" else "CANCELLED",
			"rsvp": False,
		},
	]
	for guest in guests:
		attendees.append(
			{
				"email": guest["email"],
				"name": guest["full_name"],
				"status": "NEEDS-ACTION" if method == "REQUEST" else "CANCELLED",
				"rsvp": method == "REQUEST",
			}
		)

	return generate_ics_attachment(
		event=event,
		method=method,
		organizer_email=host["email"],
		organizer_name=host["full_name"],
		attendees=attendees,
		sequence=sequence,
	)


def _send_notification(
	notification_name: str,
	event: "frappe.Document",
	context: dict,
	attachments: list | None = None,
) -> None:
	"""
	Send a notification using Frappe's Notification DocType.

	For email channel notifications, ICS attachments are included.
	Other channels (Slack, System, SMS) receive the notification without attachments.
	"""
	if not frappe.db.exists("Notification", notification_name):
		frappe.log_error(
			f"Notification '{notification_name}' not found",
			"Public Calendar Notification Error",
		)
		return

	notification = frappe.get_doc("Notification", notification_name)

	if notification.channel == "Email":
		# For email, we send manually to include ICS attachments
		recipient = context.get("recipient_email")
		if not recipient:
			return

		# Render subject and message from notification template
		subject = frappe.render_template(notification.subject, context)
		message = frappe.render_template(notification.message, context)

		try:
			frappe.sendmail(
				recipients=[recipient],
				subject=subject,
				message=message,
				attachments=attachments,
				reference_doctype="Event",
				reference_name=event.name,
				now=True,
			)
		except OutgoingEmailError:
			# Booking/reschedule/cancel flows should still complete when email is not configured.
			frappe.log_error(
				message=(
					f"Skipping email notification '{notification_name}' for Event {event.name}: "
					"no outgoing Email Account configured."
				),
				title="Public Calendar Notification Skipped",
			)
	else:
		# For other channels, use the Notification's send method
		# Temporarily inject our context into the doc for template rendering
		for key, value in context.items():
			if not hasattr(event, key):
				event.set(key, value)

		notification.send(event)


def send_booking_notification(
	event: "frappe.Document",
	public_calendar: "frappe.Document",
	recipient_email: str,
	is_host: bool = False,
) -> None:
	"""
	Send booking confirmation notification.

	Args:
	        event: The booked Event document
	        public_calendar: The Public Calendar document
	        recipient_email: Email address of the recipient
	        is_host: True if recipient is the calendar's user (host)
	"""
	host, guests = get_host_and_guests(event, public_calendar)

	if not host:
		frappe.log_error(
			f"Could not identify host for event {event.name}",
			"Public Calendar Notification Error",
		)
		return

	context = _build_notification_context(event, public_calendar, host, guests, recipient_email)

	# Get appropriate notification
	notification_field = "host_booking_notification" if is_host else "booker_booking_notification"
	notification_name = (
		public_calendar.get(notification_field) or "Public Calendar - Booking Confirmation"
	)

	# Generate ICS attachment for email notifications
	attachments = [_get_ics_attachment_for_email(event, host, guests, "REQUEST", 0)]

	_send_notification(notification_name, event, context, attachments)


def send_cancellation_notification(
	event: "frappe.Document",
	public_calendar: "frappe.Document",
	recipient_email: str,
	cancelled_by: str,
) -> None:
	"""Send cancellation notification."""
	host, guests = get_host_and_guests(event, public_calendar)

	if not host:
		return

	context = _build_notification_context(event, public_calendar, host, guests, recipient_email)
	context["cancelled_by"] = cancelled_by

	notification_name = (
		public_calendar.get("cancellation_notification") or "Public Calendar - Cancellation"
	)

	# Generate cancellation ICS
	attachments = [_get_ics_attachment_for_email(event, host, guests, "CANCEL", 1)]

	_send_notification(notification_name, event, context, attachments)


def send_reschedule_notification(
	event: "frappe.Document",
	public_calendar: "frappe.Document",
	recipient_email: str,
	rescheduled_by: str,
) -> None:
	"""Send reschedule notification with updated ICS attachment."""
	host, guests = get_host_and_guests(event, public_calendar)

	if not host:
		return

	context = _build_notification_context(event, public_calendar, host, guests, recipient_email)
	context["rescheduled_by"] = rescheduled_by

	notification_name = (
		public_calendar.get("reschedule_notification") or "Public Calendar - Reschedule"
	)

	# Generate updated ICS (sequence 1 for update)
	attachments = [_get_ics_attachment_for_email(event, host, guests, "REQUEST", 1)]

	_send_notification(notification_name, event, context, attachments)


def send_reminder(
	event: "frappe.Document",
	public_calendar: "frappe.Document",
	recipient_email: str,
) -> None:
	"""Send reminder notification for upcoming appointment."""
	host, guests = get_host_and_guests(event, public_calendar)

	if not host:
		return

	context = _build_notification_context(event, public_calendar, host, guests, recipient_email)

	notification_name = public_calendar.get("reminder_notification") or "Public Calendar - Reminder"

	_send_notification(notification_name, event, context, attachments=None)


def notify_booking(event: "frappe.Document", public_calendar: "frappe.Document") -> None:
	"""Send booking notifications based on calendar settings."""
	host, guests = get_host_and_guests(event, public_calendar)

	if not host:
		frappe.log_error(
			f"Could not identify host for event {event.name}",
			"Public Calendar Notification Error",
		)
		return

	if public_calendar.notify_host_on_booking:
		send_booking_notification(
			event=event,
			public_calendar=public_calendar,
			recipient_email=host["email"],
			is_host=True,
		)

	if public_calendar.notify_guest_on_booking:
		for guest in guests:
			send_booking_notification(
				event=event,
				public_calendar=public_calendar,
				recipient_email=guest["email"],
				is_host=False,
			)


def notify_cancellation(
	event: "frappe.Document",
	public_calendar: "frappe.Document",
	cancelled_by: str,
) -> None:
	"""Send cancellation notifications based on calendar settings."""
	if not public_calendar.notify_on_cancellation:
		return

	host, guests = get_host_and_guests(event, public_calendar)

	if not host:
		return

	# Notify all parties except the one who cancelled
	if cancelled_by != host["email"]:
		send_cancellation_notification(event, public_calendar, host["email"], cancelled_by)

	for guest in guests:
		if cancelled_by != guest["email"]:
			send_cancellation_notification(event, public_calendar, guest["email"], cancelled_by)


def notify_reschedule(
	event: "frappe.Document",
	public_calendar: "frappe.Document",
	rescheduled_by: str,
) -> None:
	"""Send reschedule notifications to affected participants."""
	host, guests = get_host_and_guests(event, public_calendar)

	if not host:
		return

	# Notify host if they didn't initiate the change
	if public_calendar.notify_host_on_booking and rescheduled_by != host["email"]:
		send_reschedule_notification(event, public_calendar, host["email"], rescheduled_by)

	# Notify guests if enabled
	if public_calendar.notify_guest_on_booking:
		for guest in guests:
			if rescheduled_by != guest["email"]:
				send_reschedule_notification(event, public_calendar, guest["email"], rescheduled_by)


# Jinja template methods (exposed via hooks.py)
def rsvp_confirm_url(event_name: str, email: str) -> str:
	"""Generate confirm RSVP URL. For use in Jinja templates."""
	return get_rsvp_url(event_name, email, "confirm")


def rsvp_decline_url(event_name: str, email: str) -> str:
	"""Generate decline RSVP URL. For use in Jinja templates."""
	return get_rsvp_url(event_name, email, "decline")


def rsvp_cancel_url(event_name: str, email: str) -> str:
	"""Generate cancel RSVP URL. For use in Jinja templates."""
	return get_rsvp_url(event_name, email, "cancel")


# Scheduled Tasks
# ---------------


def send_appointment_reminders():
	"""
	Send reminder notifications for upcoming appointments.

	Runs hourly. Finds events starting within the reminder window
	that haven't had reminders sent yet (tracked via Comment).
	"""
	# Get all calendars with reminders enabled
	calendars = frappe.get_all(
		"Public Calendar",
		filters={
			"enabled": 1,
			"send_reminder": 1,
		},
		fields=["name", "user", "reminder_minutes_before"],
	)

	if not calendars:
		return

	now = now_datetime()

	for cal in calendars:
		reminder_minutes = cal.reminder_minutes_before or 60

		# Find events starting between now and now + reminder_minutes
		window_start = now
		window_end = add_to_date(now, minutes=reminder_minutes)

		Event = DocType("Event")
		events = (
			frappe.qb.from_(Event)
			.select(Event.name)
			.where(
				(Event.reference_doctype == "Public Calendar")
				& (Event.reference_docname == cal.name)
				& (Event.status != "Cancelled")
				& (Event.starts_on >= window_start)
				& (Event.starts_on <= window_end)
			)
			.run(as_dict=True)
		)

		calendar_doc = frappe.get_doc("Public Calendar", cal.name)

		for event_data in events:
			if _reminder_already_sent(event_data.name):
				continue

			event_doc = frappe.get_doc("Event", event_data.name)
			host, guests = get_host_and_guests(event_doc, calendar_doc)

			if not host:
				continue

			try:
				send_reminder(event_doc, calendar_doc, host["email"])
			except Exception:
				frappe.log_error(
					f"Failed to send reminder for {event_doc.name} to {host['email']}",
					"Public Calendar Reminder Error",
				)

			for guest in guests:
				try:
					send_reminder(event_doc, calendar_doc, guest["email"])
				except Exception:
					frappe.log_error(
						f"Failed to send reminder for {event_doc.name} to {guest['email']}",
						"Public Calendar Reminder Error",
					)

			frappe.get_doc(
				{
					"doctype": "Comment",
					"comment_type": "Info",
					"reference_doctype": "Event",
					"reference_name": event_doc.name,
					"content": "Reminder sent",
				}
			).insert(ignore_permissions=True)


def _reminder_already_sent(event_name: str) -> bool:
	"""Check if a reminder has already been sent for this event."""
	return frappe.db.exists(
		"Comment",
		{
			"reference_doctype": "Event",
			"reference_name": event_name,
			"content": "Reminder sent",
		},
	)
