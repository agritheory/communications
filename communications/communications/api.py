# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

"""
Public Calendar API endpoints.
"""

import frappe
from frappe import _

from communications.communications.public_calendar_notifications import (
	get_public_calendar_for_event,
	notify_cancellation,
)


@frappe.whitelist()
def cancel_appointment(event: str, reason: str | None = None) -> dict:
	"""
	Cancel an appointment (authenticated endpoint).

	User must be a participant or have Event delete permission.
	"""
	if not frappe.db.exists("Event", event):
		frappe.throw(_("Event not found"), frappe.DoesNotExistError)

	event_doc = frappe.get_doc("Event", event)

	# Check permission - user must be a participant
	user = frappe.session.user
	user_email = frappe.db.get_value("User", user, "email")

	participant = None
	for p in event_doc.event_participants or []:
		if p.reference_doctype == "User" and p.reference_docname == user:
			participant = p
			break

	if not participant and not frappe.has_permission("Event", "delete", event):
		frappe.throw(_("You don't have permission to cancel this appointment"), frappe.PermissionError)

	# Get public calendar
	public_calendar = get_public_calendar_for_event(event_doc)

	# Update event and participant RSVP
	event_doc.status = "Cancelled"
	if participant:
		participant.rsvp = "Cancelled"
	if reason:
		event_doc.add_comment("Comment", text=_("Cancelled: {0}").format(reason))
	event_doc.save(ignore_permissions=True)

	# Send notifications
	if public_calendar:
		notify_cancellation(event_doc, public_calendar, user_email)

	return {
		"status": "success",
		"message": _("Appointment cancelled"),
	}
