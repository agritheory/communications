# Copyright (c) 2025, AgriTheory and contributors
# For license information, please see license.txt

"""
Event document hooks for Public Calendar.

Handles notifications when events are modified or cancelled from the Frappe desk.
"""

import frappe

from communications.communications.notifications import (
	get_public_calendar_for_event,
	notify_cancellation,
	notify_reschedule,
)
from communications.communications.video_conference import (
	handle_video_conference,
	delete_video_conference,
)


def validate(doc, method=None):
	"""Handle Event validation - create/update video conference meetings."""
	handle_video_conference(doc)


def on_update(doc, method=None):
	"""Handle Event updates - detect cancellation or reschedule."""
	# No previous state means this is the initial insert — new bookings are
	# notified via notify_booking() in book_appointment(), not here.
	if not doc.get_doc_before_save():
		return

	public_calendar = get_public_calendar_for_event(doc)
	if not public_calendar:
		return

	if doc.status == "Cancelled" and doc.has_value_changed("status"):
		_handle_cancellation(doc, public_calendar)

	elif doc.has_value_changed("starts_on") or doc.has_value_changed("ends_on"):
		_handle_reschedule(doc, public_calendar)


def on_trash(doc, method=None):
	"""Handle Event deletion - delete video conference and send cancellation."""
	# Delete video conference meeting first
	delete_video_conference(doc)

	# Send cancellation notifications
	public_calendar = get_public_calendar_for_event(doc)
	if not public_calendar:
		return

	_handle_cancellation(doc, public_calendar)


def _handle_cancellation(doc, public_calendar):
	"""Send cancellation notifications."""
	if not public_calendar.notify_on_cancellation:
		return

	cancelled_by_email = frappe.db.get_value("User", frappe.session.user, "email")
	notify_cancellation(doc, public_calendar, cancelled_by_email)


def _handle_reschedule(doc, public_calendar):
	"""Send reschedule notifications."""
	rescheduled_by_email = frappe.db.get_value("User", frappe.session.user, "email")
	notify_reschedule(doc, public_calendar, rescheduled_by_email)
