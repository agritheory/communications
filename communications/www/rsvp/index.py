# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

"""
RSVP handler at /rsvp route.

Processes RSVP actions from email links with query parameters:
/rsvp?event=EVENT-001&email=user@example.com&action=confirm&token=abc123
"""

import frappe
from frappe import _

from communications.communications.notifications import (
	get_public_calendar_for_event,
	notify_cancellation,
	verify_rsvp_token,
)


def get_context(context):
	context.no_cache = 1
	context.result = None
	context.error = None

	event = frappe.form_dict.get("event")
	email = frappe.form_dict.get("email")
	action = frappe.form_dict.get("action")
	token = frappe.form_dict.get("token")

	if not all([event, email, action, token]):
		context.error = _("Invalid link. Please use the link from your email.")
		return

	if action not in ("confirm", "decline", "cancel"):
		context.error = _("Invalid action.")
		return

	if not verify_rsvp_token(event, email, action, token):
		context.error = _("This link is invalid or has expired.")
		return

	if not frappe.db.exists("Event", event):
		context.error = _("The appointment was not found.")
		return

	event_doc = frappe.get_doc("Event", event)

	# Find participant by email
	participant = find_participant_by_email(event_doc, email)

	if not participant:
		context.error = _("You are not a participant of this event.")
		return

	public_calendar = get_public_calendar_for_event(event_doc)

	if action == "confirm":
		participant.rsvp = "Accepted"
		event_doc.save(ignore_permissions=True)
		context.result = {
			"action": "confirm",
			"message": _("Your attendance has been confirmed for {0}.").format(event_doc.subject),
		}

	elif action == "decline":
		participant.rsvp = "Declined"
		event_doc.save(ignore_permissions=True)
		if public_calendar:
			notify_cancellation(event_doc, public_calendar, email)
		context.result = {
			"action": "decline",
			"message": _("You have declined the invitation to {0}.").format(event_doc.subject),
		}

	elif action == "cancel":
		participant.rsvp = "Cancelled"
		event_doc.status = "Cancelled"
		event_doc.save(ignore_permissions=True)
		if public_calendar:
			notify_cancellation(event_doc, public_calendar, email)
		context.result = {
			"action": "cancel",
			"message": _("The appointment {0} has been cancelled.").format(event_doc.subject),
		}


def find_participant_by_email(event_doc, email):
	"""
	Find a participant in the event by email address.

	Checks User participants by their email.
	"""
	for p in event_doc.event_participants or []:
		if p.reference_doctype == "User":
			user_email = frappe.db.get_value("User", p.reference_docname, "email")
			if user_email == email:
				return p
	return None
